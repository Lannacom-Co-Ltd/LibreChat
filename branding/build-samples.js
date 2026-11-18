/**
 * Renders the sample image shown in the login page's chat examples:
 *   samples/artwork.webp   a portrait landscape, misty mountains at dawn (samples/artwork.html),
 *                          no text, so it serves every language
 * It is drawn with HTML and CSS, so it is rendered in a real browser (playwright-core from the
 * repo's node_modules, with the installed Chrome or CHROME_PATH), then shrunk and saved as WebP
 * with sharp. Run after editing samples/artwork.html:
 *   node branding/build-samples.js
 * then bump login.js?v= in docker-compose.override.yml.
 */
const path = require('path');
const root = path.join(__dirname, '..');
const sharp = require(require.resolve('sharp', { paths: [path.join(root, 'api')] }));
const { chromium } = require(require.resolve('playwright-core', { paths: [root] }));

const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
/** Shown 90px wide in the sample chat; a few times that stays sharp on high-DPI screens. */
const OUTPUT_WIDTH = 300;

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME });
  const page = await browser.newPage({ viewport: { width: 900, height: 1200 } });
  const source = 'file:///' + path.join(__dirname, 'samples', 'artwork.html').split(path.sep).join('/');
  await page.goto(source, { waitUntil: 'load' });
  await page.waitForTimeout(300);
  const png = await page.locator('#art').screenshot();
  const out = path.join(__dirname, 'samples', 'artwork.webp');
  await sharp(png).resize({ width: OUTPUT_WIDTH }).webp({ quality: 84 }).toFile(out);
  console.log('written', path.relative(root, out));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
