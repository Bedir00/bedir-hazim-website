// Usage: node render.js <startFrame> <endFrame(excl)> <out.mp4>
const { chromium } = require('playwright');
const { spawn } = require('child_process');
(async () => {
  const [, , a, b, out] = process.argv;
  const start = +a, end = +b;
  const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('pageerror:', e.message));
  await page.goto('http://127.0.0.1:8765/' + (process.env.PAGE || 'index.html') + '');
  await page.waitForFunction(() => window.__ready === true || window.__err, null, { timeout: 180000 });
  const err = await page.evaluate(() => window.__err); if (err) { console.error('ERR', err); process.exit(1); }
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-r', '30', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = start; f < end; f++) {
    await page.evaluate(t => window.renderFrame(t), f / 30);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if ((f - start) % 60 === 0) console.log(`[${start}-${end}] frame ${f} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log(`[${start}-${end}] done in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
