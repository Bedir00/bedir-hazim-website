// Rendert story.html Bild für Bild (deterministisch) und kodiert es mit ffmpeg.
//   node render.js out.mp4              -> komplettes Video (1080x1920, 30 fps)
//   node render.js --preview 1.5 4.2 …  -> Einzelbilder als PNG in preview/
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'story.html'));
  await page.evaluate(() => document.fonts.ready);
  const fps = await page.evaluate(() => window.FPS);
  const dur = await page.evaluate(() => window.DURATION);

  if (args[0] === '--preview') {
    fs.mkdirSync(path.join(__dirname, 'preview'), { recursive: true });
    for (const s of args.slice(1)) {
      const t = parseFloat(s);
      await page.evaluate(t => window.renderAt(t), t);
      await page.screenshot({ path: path.join(__dirname, 'preview', `t${t.toFixed(2)}.png`) });
    }
    await browser.close();
    return;
  }

  const out = args[0] || 'story.mp4';
  const ff = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const N = Math.round(dur * fps);
  for (let f = 0; f < N; f++) {
    await page.evaluate(t => window.renderAt(t), f / fps);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 30 === 0) process.stderr.write(`\rframe ${f}/${N}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  process.stderr.write(`\rframe ${N}/${N}\n`);
  await browser.close();
})();
