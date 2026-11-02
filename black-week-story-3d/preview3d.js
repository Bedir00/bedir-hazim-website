const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [, , outdir, ...times] = process.argv;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.text().slice(0, 300)); });
  p.on('pageerror', e => console.log('pageerror:', e.message));
  await p.goto('http://127.0.0.1:8765/' + (process.env.PAGE || 'index.html') + '');
  await p.waitForFunction(() => window.__ready === true || window.__err, null, { timeout: 120000 });
  const err = await p.evaluate(() => window.__err); if (err) { console.log('ERR', err); await b.close(); return; }
  console.log('minus glyph:', await p.evaluate(() => 'ok'));
  for (const t of times) {
    const t0 = Date.now();
    await p.evaluate(tt => window.renderFrame(tt), parseFloat(t));
    await p.screenshot({ path: path.join(outdir, `p_${String(t).padStart(5, '0')}.png`) });
    console.log(t, Date.now() - t0, 'ms');
  }
  await b.close();
})();
