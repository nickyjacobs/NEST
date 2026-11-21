import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
// node capture.mjs <dir> [fps] [times] [scene]: times is a comma-separated list of seconds for stills
// ('' for the whole animation), scene the name build.py was given (default 'scene').
const dir = process.argv[2], fps = Number(process.argv[3] || 12), only = process.argv[4], scene = process.argv[5] || 'scene';
mkdirSync(`${dir}/frames`, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 760 }, deviceScaleFactor: 1 });
await page.goto(`file://${dir}/${scene}.built.html`);
const total = await page.evaluate(() => window.TOTAL);
const times = only ? only.split(',').map(Number) : Array.from({ length: Math.ceil(total * fps) }, (_, i) => i / fps);
let i = 0;
for (const t of times) {
  await page.evaluate(t => window.render(t), t);
  await page.screenshot({ path: `${dir}/frames/${only ? 'still-' + t : String(i).padStart(4, '0')}.png` });
  i++;
}
console.log('total', total.toFixed(1), 's, frames', times.length);
await browser.close();
