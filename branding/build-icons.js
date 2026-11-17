/**
 * Builds the site logo and icons from branding/mark.svg (the green circle and orange square)
 * into branding/icons/.
 *   logo.svg                 the mark, for LibreChat's assets/logo.svg path
 *   favicons and app icons   the mark on a transparent tile for browser tabs, on the warm
 *                            off-white page colour where the OS needs an opaque tile;
 *                            favicon.ico for the admin panel
 * docker-compose.override.yml mounts these over LibreChat's own files, so no LibreChat code
 * or image changes. Re-run after changing the mark:
 *   node branding/build-icons.js
 */
const fs = require('fs');
const path = require('path');
const sharp = require(require.resolve('sharp', { paths: [path.join(__dirname, '..', 'api')] }));

const SOURCE = path.join(__dirname, 'mark.svg');
const OUT = path.join(__dirname, 'icons');
/** Opaque tiles use the light theme's page colour. */
const TILE = '#faf9f5';
/** Rendered large once, then scaled down, so small sizes stay crisp. */
const RENDER_WIDTH = 1040;

/* Tab icons are transparent so they take on the browser's own light or dark tab colour. */
const ICONS = [
  { file: 'favicon-16x16.png', size: 16, opaque: false, fill: 1 },
  { file: 'favicon-32x32.png', size: 32, opaque: false, fill: 0.96 },
  { file: 'icon-192x192.png', size: 192, opaque: false, fill: 0.86 },
  /* iOS rounds the corners itself and shows transparency as black, so use a full tile. */
  { file: 'apple-touch-icon-180x180.png', size: 180, opaque: true, fill: 0.64 },
  /* Maskable icons are cropped by the OS; keep the mark inside the 80% safe zone. */
  { file: 'maskable-icon.png', size: 512, opaque: true, fill: 0.56 },
];

/** Sizes packed into favicon.ico, used by the admin panel. */
const ICO_SIZES = [16, 24, 32, 48, 64];

const transparent = { r: 0, g: 0, b: 0, alpha: 0 };

async function icon(mark, { file, size, opaque, fill }) {
  const inner = Math.round(size * fill);
  const glyph = await sharp(mark).resize(inner, inner, { fit: 'contain', background: transparent }).toBuffer();
  const tile = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">${
    opaque ? `<rect width="${size}" height="${size}" fill="${TILE}"/>` : ''
  }</svg>`;
  await sharp(Buffer.from(tile))
    .composite([{ input: glyph, gravity: 'center' }])
    .png()
    .toFile(path.join(OUT, file));
}

/** Builds a multi-size .ico: an ICONDIR header, one entry per size, then PNG payloads. */
async function faviconIco(mark) {
  const images = await Promise.all(
    ICO_SIZES.map((size) =>
      sharp(mark).resize(size, size, { fit: 'contain', background: transparent }).png().toBuffer(),
    ),
  );
  const header = Buffer.alloc(6 + 16 * images.length);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  let offset = header.length;
  images.forEach((png, i) => {
    const entry = 6 + 16 * i;
    const size = ICO_SIZES[i];
    header.writeUInt8(size >= 256 ? 0 : size, entry);
    header.writeUInt8(size >= 256 ? 0 : size, entry + 1);
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(png.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += png.length;
  });
  return Buffer.concat([header, ...images]);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const svg = fs.readFileSync(SOURCE);
  const mark = await sharp(svg, { density: Math.round((72 * RENDER_WIDTH) / 208) }).png().toBuffer();

  fs.writeFileSync(path.join(OUT, 'logo.svg'), svg);
  await Promise.all(ICONS.map((spec) => icon(mark, spec)));
  fs.writeFileSync(path.join(OUT, 'favicon.ico'), await faviconIco(mark));

  const written = ['logo.svg', 'favicon.ico', ...ICONS.map((i) => i.file)];
  console.log(`icons written to ${OUT}: ${written.join(', ')}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
