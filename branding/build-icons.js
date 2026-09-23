/**
 * Builds the site logo and icons from branding/cmu-logo.png into branding/icons/.
 * docker-compose.override.yml mounts each output over LibreChat's own file, so no
 * LibreChat code or image changes. Re-run after replacing the source logo:
 *   node branding/build-icons.js
 * A larger (512px+) or SVG source gives sharper results on high-DPI screens.
 */
const fs = require('fs');
const path = require('path');
const sharp = require(require.resolve('sharp', { paths: [path.join(__dirname, '..', 'api')] }));

const SOURCE = path.join(__dirname, 'cmu-logo.png');
const OUT = path.join(__dirname, 'icons');

const ICONS = [
  { file: 'favicon-16x16.png', size: 16 },
  { file: 'favicon-32x32.png', size: 32 },
  { file: 'apple-touch-icon-180x180.png', size: 180, background: '#ffffff', padding: 0.08 },
  { file: 'icon-192x192.png', size: 192 },
  /* Maskable icons are cropped to a circle or squircle by the OS; keep the emblem inside
     the 80% safe zone on a solid background. */
  { file: 'maskable-icon.png', size: 512, background: '#ffffff', padding: 0.12 },
];

async function icon({ file, size, background, padding = 0 }) {
  const inner = Math.round(size * (1 - padding * 2));
  const emblem = await sharp(SOURCE)
    .resize(inner, inner, { fit: 'contain', kernel: 'lanczos3' })
    .toBuffer();
  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: background ?? { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite([{ input: emblem, gravity: 'center' }])
    .png()
    .toFile(path.join(OUT, file));
}

/** The login page loads `assets/logo.svg`, so wrap the raster emblem in an SVG. */
async function logoSvg() {
  const png = await sharp(SOURCE).png().toBuffer();
  const { width, height } = await sharp(SOURCE).metadata();
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}"><image width="${width}" height="${height}" href="data:image/png;base64,${png.toString('base64')}"/></svg>\n`;
  fs.writeFileSync(path.join(OUT, 'logo.svg'), svg);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  await Promise.all([...ICONS.map(icon), logoSvg()]);
  console.log(`icons written to ${OUT}: ${[...ICONS.map((i) => i.file), 'logo.svg'].join(', ')}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
