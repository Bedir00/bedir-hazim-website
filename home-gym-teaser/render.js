// Usage: node render.js <key> [stills]   renders out/<key>.silent.mp4 (or stills)
const http = require('http'), fs = require('fs'), path = require('path'), { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright');
const dir = __dirname, key = process.argv[2], stills = process.argv[3] === 'stills';
const FPS = 30, LEAD = 0.5, GAP = 0.35, TAIL = 1.7;
const cfg = JSON.parse(fs.readFileSync(path.join(dir, 'scripts.json'), 'utf8'))[key];
const dur = [0, 1, 2].map(i => parseFloat(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path.join(dir, `vo/${key}-${i}.wav`)]).toString()));
const s0 = LEAD, s1 = s0 + dur[0] + GAP, s2 = s1 + dur[1] + GAP, end = s2 + dur[2] + TAIL;
const timeline = { s0, s1, s2, end };
fs.mkdirSync(path.join(dir, 'out'), { recursive: true });
fs.writeFileSync(path.join(dir, `out/${key}.timeline.json`), JSON.stringify(timeline));
const types = { '.html': 'text/html', '.js': 'text/javascript', '.woff2': 'font/woff2' };
const server = http.createServer((req, res) => {
  const p = path.join(dir, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(dir) || !fs.existsSync(p)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
}).listen(0, async () => {
  const port = server.address().port;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => console.error('pageerror', e.message));
  await page.goto(`http://localhost:${port}/stage.html`);
  await page.waitForFunction(() => window.ready === true);
  await page.evaluate(([c, t]) => window.setup(c, t), [cfg, timeline]);
  if (stills) {
    const times = [0.15, s0 + 1.2, s1 + 0.4, s1 + dur[1] - 0.2, s2 + 1.6, end - 0.6];
    for (const t of times) {
      await page.evaluate(t => window.frame(t), t);
      await page.screenshot({ path: path.join(dir, `out/${key}-still-${t.toFixed(1)}.jpg`), type: 'jpeg', quality: 85 });
    }
  } else {
    const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', path.join(dir, `out/${key}.silent.mp4`)], { stdio: ['pipe', 'inherit', 'inherit'] });
    const frames = Math.round(end * FPS), t0 = Date.now();
    for (let i = 0; i < frames; i++) {
      await page.evaluate(t => window.frame(t), i / FPS);
      const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 60 === 0) console.log(key, `${i}/${frames}`, ((Date.now() - t0) / 1000).toFixed(0) + 's');
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }
  await browser.close(); server.close();
  console.log(key, 'done', JSON.stringify(timeline));
});
