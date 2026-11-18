/**
 * Renders the sample images shown in the login page's chat examples:
 *   samples/artwork.webp                       a portrait landscape, misty mountains at dawn
 *                                              (samples/artwork.html), no text, every language
 *   samples/poster-en.webp, samples/poster-th.webp   a launch poster (samples/poster.html, ?lang=th)
 * They are drawn with HTML and CSS, so they are rendered in a real browser (playwright-core
 * from the repo's node_modules, with the installed Chrome or CHROME_PATH), then shrunk and
 * saved as WebP with sharp. Run after editing a sample:
 *   node branding/build-samples.js
 * then bump login.js?v= in docker-compose.override.yml.
 */
const path = require('path');
const root = path.join(__dirname, '..');
const sharp = require(require.resolve('sharp', { paths: [path.join(root, 'api')] }));
const { chromium } = require(require.resolve('playwright-core', { paths: [root] }));

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
/** Each image is shown small in the sample chat; a few times that size stays sharp on high-DPI screens. */
const SAMPLES = [
  { source: 'artwork.html', out: 'artwork.webp', viewport: { width: 900, height: 1200 }, width: 300 },
  { source: 'poster.html?lang=en', out: 'poster-en.webp', viewport: { width: 1600, height: 900 }, width: 528 },
  { source: 'poster.html?lang=th', out: 'poster-th.webp', viewport: { width: 1600, height: 900 }, width: 528 },
];

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  for (const sample of SAMPLES) {
    const page = await browser.newPage({ viewport: sample.viewport });
    const [file, query = ''] = sample.source.split('?');
    const url = 'file:///' + path.join(__dirname, 'samples', file).split(path.sep).join('/') + (query ? `?${query}` : '');
    await page.goto(url, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    const png = await page.screenshot();
    const out = path.join(__dirname, 'samples', sample.out);
    await sharp(png).resize({ width: sample.width }).webp({ quality: 84 }).toFile(out);
    console.log('written', path.relative(root, out));
    await page.close();
  }
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
