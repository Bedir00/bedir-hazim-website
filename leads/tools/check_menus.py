"""Check restaurant websites for weak menus (none online, PDF/scan/photo only, poor mobile design).

usage: python3 check_menus.py restaurants.json out.jsonl LIMIT [SEED]
"""
import asyncio, io, json, random, re, sys, collections
import requests
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from pypdf import PdfReader

CHROME = '/opt/pw-browsers/chromium'
CONCURRENCY = 8
MENU_RE = re.compile(r'speise|men[uü]|karte|carte|gerichte|mittagstisch|lunch|food|essen\b|angebot', re.I)
STRONG_RE = re.compile(r'speisekarte|men[uü]karte|unsere karte|zur karte|menu|men[uü]', re.I)
SKIP_RE = re.compile(r'getr[aä]nke|wein|drink|cocktail|bar\b|impressum|datenschutz|kontakt|jobs|gutschein', re.I)
PLATFORMS = ('lieferando', 'wolt.com', 'ubereats', 'speisekarte.de', 'speisekarte.menu', 'foodbooking',
             'gloriafood', 'order.', 'dish.co', 'resmio', 'menu.app', 'qr-', 'flipsnack', 'issuu', 'yumpu',
             'instagram.com', 'facebook.com')
PRICE_RE = re.compile(r'(?:\d{1,3}[,.]\d{2}\s*(?:€|eur\b|euro\b))|(?:€\s*\d{1,3}(?:[,.]\d{2})?)|(?:\b\d{1,2},(?:\d{2}|-)(?!\d))|(?:\b\d{1,2}\s*€)', re.I)
CHAINS = re.compile(r"l'osteria|vapiano|block house|hans im gl|peter pane|maredo|nordsee|vapiano|sausalitos|"
                    r"burger king|mcdonald|kfc|subway|pizza hut|domino|alex\b|extrablatt|enchilada|wienerwald|"
                    r"hallo pizza|joey|losteria|cinnamood|five guys|dean & david|coa\b|sticks'n'sushi|ruby", re.I)


def domain(u):
    try:
        return urlparse(u if '//' in u else 'http://' + u).netloc.lower().removeprefix('www.')
    except Exception:
        return ''


async def page_info(page):
    for _ in range(8):
        await page.mouse.wheel(0, 900)
        await page.wait_for_timeout(250)
    await page.wait_for_timeout(800)
    html = await page.content()
    pdfs = [urljoin(page.url, u) for u in re.findall(r'''["'(=]((?:https?:)?[^"'()\s<>]+?\.pdf)(?:[?#][^"'\s<>]*)?["')&]''', html, re.I)]
    info = await page.evaluate("""() => {
      const links = [...document.querySelectorAll('a[href], iframe[src], embed[src], object[data]')].map(a => ({
        href: a.href || a.src || a.data || '', text: (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().slice(0, 80),
        tag: a.tagName}));
      const imgs = [...document.images].filter(i => i.naturalWidth >= 450 && i.naturalHeight >= 450 && i.getBoundingClientRect().width >= 250).length;
      const menuImgs = [...document.images].map(i => i.currentSrc || i.src || '')
        .filter(u => /speise|karte|menu|men%C3%BC|menü/i.test(u.split('/').pop())).length;
      return {
        menuImgs,
        text: document.body ? document.body.innerText : '',
        links, bigImages: imgs,
        viewport: !!document.querySelector('meta[name=viewport]'),
        scrollW: document.documentElement.scrollWidth,
        frames: document.querySelectorAll('frameset, frame').length,
        title: document.title,
      };
    }""")
    info['pdfs'] = list(dict.fromkeys(pdfs))
    info['shop'] = bool(re.search(r'warenkorb|in den korb|add to cart|jetzt bestellen', info['text'], re.I))
    return info


def _get(url):
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    return r.content


async def check_pdf(ctx, url):
    try:
        body = await asyncio.to_thread(_get, url)
        if not body.startswith(b'%PDF'):
            return {'ok': False}
        reader = PdfReader(io.BytesIO(body))
        pages = len(reader.pages)
        chars = sum(len((p.extract_text() or '').strip()) for p in reader.pages[:6])
        per_page = chars / max(1, min(pages, 6))
        return {'ok': True, 'mb': round(len(body) / 1e6, 1), 'pages': pages, 'scan': per_page < 80,
                'prices': len(PRICE_RE.findall(' '.join((p.extract_text() or '') for p in reader.pages[:6])))}
    except Exception as e:
        return {'ok': False, 'err': str(e)[:100]}


def classify_links(info, base):
    base_dom = domain(base)
    cands = []
    for l in info['links']:
        h = l['href']
        if not h or h.startswith(('mailto:', 'tel:', 'javascript:')):
            continue
        hl, tl = h.lower(), l['text'].lower()
        path = urlparse(h).path.lower()
        is_pdf = '.pdf' in hl
        is_img = path.endswith(('.jpg', '.jpeg', '.png', '.webp'))
        hit = MENU_RE.search(tl) or MENU_RE.search(path) or (is_pdf and MENU_RE.search(hl))
        if not hit:
            continue
        if SKIP_RE.search(tl) and not STRONG_RE.search(tl):
            continue
        if h.split('#')[0].rstrip('/') == base.split('#')[0].rstrip('/'):
            continue
        kind = 'pdf' if is_pdf else 'img' if is_img else 'platform' if any(p in hl for p in PLATFORMS) \
            else 'html' if domain(h) == base_dom else 'external'
        score = (3 if re.search('speise', tl + hl) else 0) + (2 if STRONG_RE.search(tl) else 0) + (1 if is_pdf else 0)
        cands.append({'href': h, 'text': l['text'], 'kind': kind, 'score': score})
    cands.sort(key=lambda c: -c['score'])
    seen, out = set(), []
    for c in cands:
        if c['href'] not in seen:
            seen.add(c['href']); out.append(c)
    return out


def design_flags(info, final_url):
    flags = []
    if not info['viewport']:
        flags.append('nicht für Handys optimiert (kein Viewport)')
    if info['scrollW'] > 430:
        flags.append(f"seitliches Scrollen am Handy nötig ({info['scrollW']}px breit)")
    if final_url.startswith('http://'):
        flags.append('keine sichere Verbindung (kein HTTPS)')
    if info['frames']:
        flags.append('veraltete Frame-Technik')
    years = [int(y) for y in re.findall(r'(?:©|\(c\)|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})', info['text'], re.I)]
    if years and max(years) <= 2020:
        flags.append(f'Copyright-Jahr {max(years)}')
    return flags


async def check_site(browser, r):
    url = r['website'].strip()
    if not url.startswith('http'):
        url = 'https://' + url
    res = dict(r, url=url)
    ctx = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                                    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 '
                                               '(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
                                    locale='de-DE', ignore_https_errors=True)
    page = await ctx.new_page()
    try:
        resp = await page.goto(url, timeout=25000, wait_until='domcontentloaded')
        await page.wait_for_timeout(2500)
        if not resp or resp.status >= 400:
            res['status'] = f'http {resp.status if resp else "?"}'
            return res
        final = page.url
        info = await page_info(page)
        res['final_url'] = final
        if domain(final) != domain(url) and any(p in final for p in ('facebook.', 'instagram.', 'lieferando', 'google.')):
            res['status'] = 'redirect_platform'
            return res
        if len(info['text'].strip()) < 40 and info['bigImages'] == 0 and not info['frames']:
            res['status'] = 'empty'
            return res
        res['status'] = 'ok'
        res['design'] = design_flags(info, final)
        res['home_prices'] = len(PRICE_RE.findall(info['text']))
        res['home_menu_word'] = bool(re.search(r'speisekarte|unsere karte', info['text'], re.I))
        res['home_menu_imgs'] = info['menuImgs']
        links = classify_links(info, final)
        res['menu_links'] = links[:6]
        menu = {'kind': None}
        home_pdfs = [u for u in info['pdfs'] if MENU_RE.search(u) and not SKIP_RE.search(u)]
        if not links and home_pdfs:
            links = [{'href': home_pdfs[0], 'text': '', 'kind': 'pdf', 'score': 1}]
        if not links:
            # no menu link: look at unnamed PDFs (Wix etc.) and one "Restaurant/Küche" page
            pages = [(info, final)]
            alt = [l['href'] for l in info['links'] if l['tag'] == 'A' and domain(l['href']) == domain(final)
                   and re.search(r'gastronomie|restaurant|k[uü]che|kueche|essen|speisen', l['text'], re.I)
                   and l['href'].split('#')[0].rstrip('/') != final.split('#')[0].rstrip('/')]
            if alt:
                try:
                    await page.goto(alt[0], timeout=25000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(2500)
                    ai = await page_info(page)
                    pages.append((ai, page.url))
                    res['alt_page'] = page.url
                except Exception:
                    pass
            for pi, purl in pages:
                if len(PRICE_RE.findall(pi['text'])) >= 8:
                    res['home_prices'] = max(res['home_prices'], len(PRICE_RE.findall(pi['text'])))
                    break
                pdfs = [u for u in pi['pdfs'] if not re.search(r'agb|datenschutz|impressum|privacy|widerruf', u, re.I)]
                found = None
                for u in pdfs[:3]:
                    pc = await check_pdf(ctx, u)
                    if pc.get('ok') and (pc['scan'] or pc['prices'] >= 5):
                        found = (u, pc)
                        break
                if found:
                    links = [{'href': found[0], 'text': '', 'kind': 'pdf', 'score': 0}]
                    break
                if pi['menuImgs']:
                    res['home_menu_imgs'] = pi['menuImgs']
                    res['final_url'] = purl
                    break
        res['shop'] = info['shop']
        if links:
            best = links[0]
            menu = {'kind': best['kind'], 'href': best['href']}
            if best['kind'] == 'html':
                try:
                    await page.goto(best['href'], timeout=25000, wait_until='domcontentloaded')
                    await page.wait_for_timeout(2500)
                    mi = await page_info(page)
                    if len(PRICE_RE.findall(mi['text'])) < 8 and not mi['pdfs']:
                        nxt = [l for l in classify_links(mi, page.url) if l['kind'] == 'html' and l['score'] >= 2
                               and l['href'].split('#')[0] not in (best['href'].split('#')[0], final.split('#')[0])]
                        if nxt:
                            menu['hop2'] = nxt[0]['href']
                            await page.goto(nxt[0]['href'], timeout=25000, wait_until='domcontentloaded')
                            await page.wait_for_timeout(2500)
                            mi = await page_info(page)
                    menu['shop'] = mi['shop']
                    menu['url'] = page.url
                    menu['prices'] = len(PRICE_RE.findall(mi['text']))
                    menu['bigImages'] = mi['bigImages'] + mi['menuImgs']
                    sub = classify_links(mi, page.url)
                    pdfs = [l for l in sub if l['kind'] == 'pdf']
                    plats = [l for l in sub if l['kind'] in ('platform', 'external')]
                    imgs = [l for l in sub if l['kind'] == 'img']
                    embeds = [l['href'] for l in mi['links'] if l['tag'] in ('IFRAME', 'EMBED', 'OBJECT') and '.pdf' in l['href'].lower()]
                    menu['pdf'] = (embeds or [p['href'] for p in pdfs] or [u for u in mi['pdfs'] if MENU_RE.search(u) and not SKIP_RE.search(u)] or [None])[0]
                    menu['platform'] = plats[0]['href'] if plats else None
                    menu['img'] = imgs[0]['href'] if imgs else None
                    if not res['design']:
                        res['design'] = design_flags(mi, page.url)
                except Exception as e:
                    menu['err'] = str(e)[:100]
            pdf_url = menu.get('pdf') or (best['href'] if best['kind'] == 'pdf' else None)
            if pdf_url:
                menu['pdf_url'] = pdf_url
                menu['pdf_check'] = await check_pdf(ctx, pdf_url)
        res['menu'] = menu
        return res
    except Exception as e:
        res['status'] = 'error: ' + str(e).split('\n')[0][:120]
        return res
    finally:
        await ctx.close()


def verdict(r):
    """Return (category, reason, menu_link) or None if not a lead."""
    if r.get('status') != 'ok' or r.get('final_url', '').startswith('chrome-error'):
        return None
    m, d = r.get('menu', {}), r.get('design', [])
    kind = m.get('kind')
    pc = m.get('pdf_check') or {}
    if kind == 'html' and m.get('prices', 0) >= 8:
        return ('Schlechtes Design', '; '.join(d), m['href']) if len(d) >= 2 else None
    if r.get('shop') or m.get('shop'):
        return None  # own online ordering shop
    if kind in ('platform', 'external') or (kind == 'html' and m.get('platform') and not m.get('pdf')):
        return None  # menu lives on an ordering platform / external tool – not clearly weak
    if pc.get('ok'):
        if pc['scan']:
            why = f"Karte nur als eingescanntes PDF ohne Text ({pc['pages']} S., {pc['mb']} MB) – am Handy schwer lesbar, nicht von Google auffindbar"
        else:
            why = f"Karte nur als PDF-Download ({pc['pages']} S., {pc['mb']} MB) – am Handy zoomen nötig"
        if d:
            why += '; Website: ' + '; '.join(d)
        return ('Nur PDF/Scan', why, m['pdf_url'])
    if kind == 'img' or (kind == 'html' and m.get('prices', 0) < 3 and (m.get('img') or m.get('bigImages', 0) >= 1)):
        if kind == 'html' and not m.get('img') and m.get('bigImages', 0) < 2 and not re.search('speise|karte|men', m['href'], re.I):
            return None
        why = 'Karte nur als Foto/Bild – nicht durchsuchbar, am Handy schwer lesbar'
        if d:
            why += '; Website: ' + '; '.join(d)
        return ('Nur PDF/Scan', why, m.get('url') or m.get('img') or m['href'])
    if kind is None and r.get('home_menu_imgs'):
        why = 'Karte nur als Foto/Bild auf der Startseite – nicht durchsuchbar, am Handy schwer lesbar'
        if d:
            why += '; Website: ' + '; '.join(d)
        return ('Nur PDF/Scan', why, r.get('final_url', ''))
    if kind is None and r.get('home_prices', 0) < 5:
        why = ('Nur ein kurzer Auszug der Karte auf der Startseite, ohne Preise' if r.get('home_menu_word')
               else 'Keine Speisekarte auf der Website gefunden')
        if d:
            why += '; Website: ' + '; '.join(d)
        return ('Keine Online-Karte', why, '')
    if len(d) >= 2:
        return ('Schlechtes Design', '; '.join(d), m.get('url') or m.get('href', ''))
    return ('UNKLAR', '', m.get('url') or m.get('href', ''))


async def main():
    src, out, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    rows = json.load(open(src))
    doms = collections.Counter(domain(r['website']) for r in rows)
    done = set()
    try:
        done = {json.loads(l)['osm'] for l in open(out)}
    except FileNotFoundError:
        pass
    pool, seen = [], set()
    for r in rows:
        dm = domain(r['website'])
        if doms[dm] > 2 or CHAINS.search(r['name']) or dm in seen or r['osm'] in done:
            continue
        seen.add(dm); pool.append(r)
    random.Random(seed).shuffle(pool)
    pool = pool[:limit]
    print(f'{len(pool)} sites to check', flush=True)
    sem = asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        n = 0

        async def run(r):
            nonlocal n
            async with sem:
                try:
                    res = await asyncio.wait_for(check_site(browser, r), 120)
                except Exception as e:
                    res = dict(r, status='timeout ' + str(e)[:60])
            res['verdict'] = verdict(res)
            with open(out, 'a') as f:
                f.write(json.dumps(res, ensure_ascii=False) + '\n')
            n += 1
            if n % 20 == 0:
                print(n, flush=True)
        await asyncio.gather(*(run(r) for r in pool))
        await browser.close()

asyncio.run(main())
