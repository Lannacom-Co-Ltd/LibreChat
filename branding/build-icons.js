/**
 * Builds the site logo and icons from branding/cmubs-logo.png into branding/icons/.
 *   logo-light.png / logo-dark.png  the full CMUBS logo, trimmed; the dark variant lifts the
 *                                   grey "Chiang Mai University Business School" line so it
 *                                   stays legible on the black login backdrop
 *   logo.svg                        the light logo wrapped for LibreChat's assets/logo.svg path
 *   favicons and app icons          the dot mark alone (the wordmark is unreadable at 16px):
 *                                   transparent for browser tabs, white-backed where the OS
 *                                   needs an opaque tile; favicon.ico for the admin panel
 * docker-compose.override.yml mounts these over LibreChat's own files, so no LibreChat code
 * or image changes. Re-run after replacing the source logo:
 *   node branding/build-icons.js
 * A larger (1024px+) or SVG source gives sharper results on high-DPI screens.
 */
const fs = require('fs');
const path = require('path');
const sharp = require(require.resolve('sharp', { paths: [path.join(__dirname, '..', 'api')] }));

const SOURCE = path.join(__dirname, 'cmubs-logo.png');
const OUT = path.join(__dirname, 'icons');

/** Region of the source holding the dot mark (left of the "CMU" wordmark, above the wave). */
const MARK_REGION = { left: 40, top: 105, width: 160, height: 223 };

/** Greys darker than this, and nearly unsaturated, are the subtitle text. */
const SUBTITLE_MAX_LUMA = 140;
const SUBTITLE_MAX_CHROMA = 24;
const SUBTITLE_ON_DARK = [228, 226, 236];

/* Tab icons are transparent so they take on the browser's own light or dark tab colour. */
const ICONS = [
  { file: 'favicon-16x16.png', size: 16, shape: 'none', fill: 1 },
  { file: 'favicon-32x32.png', size: 32, shape: 'none', fill: 0.96 },
  { file: 'icon-192x192.png', size: 192, shape: 'none', fill: 0.9 },
  /* iOS rounds the corners itself and shows transparency as black, so use a full square. */
  { file: 'apple-touch-icon-180x180.png', size: 180, shape: 'square', fill: 0.66 },
  /* Maskable icons are cropped by the OS; keep the mark inside the 80% safe zone. */
  { file: 'maskable-icon.png', size: 512, shape: 'square', fill: 0.56 },
];

const trimmedLogo = () => sharp(SOURCE).trim({ threshold: 10 }).png().toBuffer();

async function darkLogo(light) {
  const { data, info } = await sharp(light).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) {
    const [r, g, b, a] = [data[i], data[i + 1], data[i + 2], data[i + 3]];
    if (a === 0) {
      continue;
    }
    const luma = 0.299 * r + 0.587 * g + 0.114 * b;
    const chroma = Math.max(r, g, b) - Math.min(r, g, b);
    if (luma < SUBTITLE_MAX_LUMA && chroma < SUBTITLE_MAX_CHROMA) {
      [data[i], data[i + 1], data[i + 2]] = SUBTITLE_ON_DARK;
    }
  }
  return sharp(data, { raw: info }).png().toBuffer();
}

async function icon(mark, { file, size, shape, fill }) {
  const inner = Math.round(size * fill);
  const glyph = await sharp(mark)
    .resize(inner, inner, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .toBuffer();
  const backgrounds = {
    none: '',
    circle: `<circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="#ffffff"/>`,
    square: `<rect width="${size}" height="${size}" fill="#ffffff"/>`,
  };
  const badge = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">${backgrounds[shape]}</svg>`;
  await sharp(Buffer.from(badge))
    .composite([{ input: glyph, gravity: 'center' }])
    .png()
    .toFile(path.join(OUT, file));
}

/** Sizes packed into favicon.ico, used by the admin panel. */
const ICO_SIZES = [16, 24, 32, 48, 64];

/** Builds a multi-size .ico: an ICONDIR header, one entry per size, then PNG payloads. */
async function faviconIco(mark) {
  const images = await Promise.all(
    ICO_SIZES.map((size) =>
      sharp(mark)
        .resize(size, size, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
        .png()
        .toBuffer(),
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

function logoSvg(png, { width, height }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}"><image width="${width}" height="${height}" href="data:image/png;base64,${png.toString('base64')}"/></svg>\n`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const light = await trimmedLogo();
  const dark = await darkLogo(light);
  const size = await sharp(light).metadata();
  /* sharp trims before it extracts within one pipeline, so crop first, then trim. */
  const region = await sharp(SOURCE).extract(MARK_REGION).png().toBuffer();
  const mark = await sharp(region).trim({ threshold: 10 }).png().toBuffer();

  fs.writeFileSync(path.join(OUT, 'logo-light.png'), light);
  fs.writeFileSync(path.join(OUT, 'logo-dark.png'), dark);
  fs.writeFileSync(path.join(OUT, 'logo.svg'), logoSvg(light, size));
  fs.writeFileSync(path.join(OUT, 'mark.png'), mark);
  await Promise.all(ICONS.map((spec) => icon(mark, spec)));
  fs.writeFileSync(path.join(OUT, 'favicon.ico'), await faviconIco(mark));

  const written = [
    'logo-light.png',
    'logo-dark.png',
    'logo.svg',
    'mark.png',
    'favicon.ico',
    ...ICONS.map((i) => i.file),
  ];
  console.log(`icons written to ${OUT} (logo ${size.width}x${size.height}): ${written.join(', ')}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
