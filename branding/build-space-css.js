/**
 * Generates branding/space.css: a premium animated backdrop for the LibreChat login page.
 *   Dark theme  -> orbit view: black space, fine star dust, a planet horizon with a thin
 *                  atmospheric rim and a sunrise flare behind the login card.
 *   Light theme -> above the clouds at dawn: pearl-to-peach sky, a soft sun with slow
 *                  light rays, and a drifting sea of volumetric clouds.
 * Pure CSS, injected at container start — see docker-compose.override.yml. After editing:
 *   node branding/build-space-css.js
 * then bump ?v= in docker-compose.override.yml and recreate the api container.
 */
const fs = require('fs');
const path = require('path');

let seed = 20260923;
const rand = () => {
  seed = (seed * 1664525 + 1013904223) % 4294967296;
  return seed / 4294967296;
};
const between = (min, max) => min + rand() * (max - min);
const pick = (list) => list[Math.floor(rand() * list.length)];
const join = (layers) => layers.join(',\n    ');
const px = (n) => `${Math.round(n)}px`;

/** One tile of stars as radial-gradient layers. */
function starTile({ count, tile, sizes, colors, glow = 0 }) {
  const layers = [];
  for (let i = 0; i < count; i++) {
    const x = px(rand() * tile);
    const y = px(rand() * tile);
    const size = pick(sizes);
    layers.push(`radial-gradient(${size}px ${size}px at ${x} ${y}, ${pick(colors)}, transparent)`);
    if (glow > 0) {
      const halo = size * 4;
      layers.push(`radial-gradient(${halo}px ${halo}px at ${x} ${y}, rgba(180, 200, 255, ${glow}), transparent)`);
    }
  }
  return join(layers);
}

/**
 * A band of soft cloud puffs along the bottom of a tile. Each puff is a sunlit top over a
 * cooler, shaded body, and fades out from its centre, so overlaps read as volume rather
 * than outlines. Puffs are repeated one tile to each side so none is cut at a tile seam.
 */
function cloudBand({ count, tile, height, rx, ry, top, light, shade }) {
  const layers = [];
  for (let i = 0; i < count; i++) {
    const cx = ((i + between(0.1, 0.9)) / count) * tile;
    const y = between(top, height);
    const w = between(...rx);
    const h = between(...ry);
    for (const x of [cx - tile, cx, cx + tile]) {
      if (x + w < 0 || x - w > tile) {
        continue;
      }
      layers.push(
        `radial-gradient(ellipse ${px(w * 0.7)} ${px(h * 0.62)} at ${px(x - w * 0.08)} ${px(y - h * 0.3)}, rgba(${light}, 0.95) 0%, rgba(${light}, 0.55) 40%, rgba(${light}, 0) 72%)`,
        `radial-gradient(ellipse ${px(w)} ${px(h)} at ${px(x)} ${px(y)}, rgba(${shade}, 0.95) 0%, rgba(${shade}, 0.7) 40%, rgba(${shade}, 0) 72%)`,
      );
    }
  }
  return join(layers);
}

/** Thin, high cirrus wisps. */
function wisps({ count, tile, height }) {
  const layers = [];
  for (let i = 0; i < count; i++) {
    const x = px(((i + between(0.1, 0.9)) / count) * tile);
    const y = px(between(40, height));
    layers.push(
      `radial-gradient(ellipse ${px(between(180, 340))} ${px(between(14, 28))} at ${x} ${y}, rgba(255, 255, 255, 0.32), transparent 70%)`,
    );
  }
  return join(layers);
}

const LOGO_VERSION = 1;
const LOGIN_TITLE = 'Welcome to CMUBS AI Hub';
const DRIFT_TILE = 700;
const TWINKLE_A_TILE = 523;
const TWINKLE_B_TILE = 431;
const CLOUD_BACK = { tile: 1800, height: 420 };
const CLOUD_FRONT = { tile: 2200, height: 360 };
const WISP = { tile: 2400, height: 460 };

const starDust = starTile({
  count: 70,
  tile: DRIFT_TILE,
  sizes: [0.8, 1, 1, 1, 1.2, 1.5],
  colors: ['rgba(255,255,255,0.7)', 'rgba(205,220,255,0.55)', 'rgba(255,240,225,0.5)'],
});
const twinkleA = starTile({
  count: 7,
  tile: TWINKLE_A_TILE,
  sizes: [1.4, 1.8, 2.2],
  colors: ['#ffffff', 'rgba(215,228,255,0.95)'],
  glow: 0.12,
});
const twinkleB = starTile({
  count: 6,
  tile: TWINKLE_B_TILE,
  sizes: [1.4, 1.8, 2.2],
  colors: ['#ffffff', 'rgba(255,238,215,0.95)'],
  glow: 0.12,
});
const cloudsBack = cloudBand({
  count: 22,
  ...CLOUD_BACK,
  rx: [140, 280],
  ry: [60, 120],
  top: 170,
  light: '255, 246, 240',
  shade: '222, 218, 238',
});
const cloudsFront = cloudBand({
  count: 18,
  ...CLOUD_FRONT,
  rx: [200, 360],
  ry: [70, 130],
  top: 150,
  light: '255, 255, 255',
  shade: '232, 230, 244',
});
const cirrus = wisps({ count: 5, ...WISP });

/* Only the login screen renders the login form, so `:has()` scopes every rule to it
   (not register or password reset) without touching LibreChat's markup. LibreChat puts
   `dark` or `light` on <html>, which picks the theme. */
const AUTH = 'div:has(> main):has(form[aria-label="Login form"])';
const LOGO = `${AUTH} div:has(> img[src="assets/logo.svg"])`;
const CARD = `${AUTH} > main > div`;
const BUTTON = `${AUTH} [data-testid="login-button"]`;
const DARK = `html.dark ${AUTH}`;
const DARK_LOGO = `html.dark ${LOGO}`;
const LIGHT = `html:not(.dark) ${AUTH}`;
const LIGHT_LOGO = `html:not(.dark) ${LOGO}`;

/** A layer anchored to the bottom that scrolls sideways one tile per cycle (seamless). */
const bottomScroller = ({ tile, height }, viewportShare) => `
  bottom: 0;
  left: -${tile}px;
  width: calc(100vw + ${tile}px);
  height: ${viewportShare};
  background-size: ${tile}px ${height}px;
  background-position: 0 100%;
  background-repeat: repeat-x;
  will-change: transform;`;

const css = `/* Generated by branding/build-space-css.js — edit that file, not this one. */

/* ================================ Shared ================================ */

${AUTH} {
  --cmu-purple: #5b2c83;
  --cmu-purple-light: #8a55c9;
  --cmu-gold: #c9a45c;
  isolation: isolate;
  overflow: hidden;
}

${AUTH}::before,
${AUTH}::after,
${AUTH} > main::before,
${AUTH} > main::after,
${LOGO}::before,
${LOGO}::after {
  content: '';
  position: fixed;
  z-index: -1;
  pointer-events: none;
}

/* Backmost layers (star dust / sun and rays) sit behind the horizon and clouds. */
${AUTH}::before,
${AUTH}::after {
  z-index: -2;
}

/* LibreChat serves assets/logo.svg with a two-day browser cache, so a browser that saw the
   old logo keeps it. Swapping the image through a versioned URL here takes effect on the
   next page load everywhere the logo appears. Bump LOGO_VERSION after changing the logo. */
img[src="assets/logo.svg"] {
  content: url('icons/logo.svg?v=${LOGO_VERSION}');
}

/* Larger emblem with a soft halo, taken out of the flow so the card centres on the whole
   screen instead of on the space below the logo. The filter sits on the image, not the
   wrapper, so the wrapper's fixed-position scene layers stay anchored to the viewport. */
${LOGO} {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: clamp(110px, 17vh, 170px);
  margin-top: clamp(20px, 4vh, 48px);
}

/* The footer (privacy / terms links) likewise floats at the bottom, so it doesn't push the
   card off-centre either. */
${AUTH} > [role='contentinfo'] {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
}

/* Custom heading. LibreChat has no setting for the login title, so the original text is
   collapsed and replaced visually (screen readers still announce the original). */
${CARD} > h1 {
  font-size: 0;
  line-height: 0;
}

${CARD} > h1::after {
  content: '${LOGIN_TITLE}';
  display: block;
  font-size: clamp(1.375rem, 6vw, 1.625rem);
  line-height: 2.25rem;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

/* Layered glass card with a purple-to-gold hairline border. */
${CARD} {
  border: 1px solid transparent;
  border-radius: 20px;
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  backdrop-filter: blur(18px) saturate(140%);
}

${BUTTON} {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--cmu-purple-light) 0%, var(--cmu-purple) 55%, #43206a 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.28),
    0 12px 28px -10px rgba(91, 44, 131, 0.75);
  transition: transform 0.2s ease, filter 0.2s ease, box-shadow 0.2s ease;
}

${BUTTON}:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 16px 34px -10px rgba(91, 44, 131, 0.85);
}

/* ============================ Dark: orbit view ============================ */

${DARK} {
  /* Dark theme tokens (client/src/style.css .dark) keep the form legible on black. */
  --text-primary: var(--gray-100);
  --text-secondary: var(--gray-300);
  --text-secondary-alt: var(--gray-400);
  --text-tertiary: var(--gray-400);
  --surface-primary: var(--gray-900);
  --border-light: 44 40 58;
  --border-medium: 70 64 92;
  --accent-primary: 176 132 240;
  --accent-primary-hover: 200 166 250;
  color-scheme: dark;
  background: #000;
}

/* Fine, slowly drifting star dust. */
${DARK}::before {
  top: -${DRIFT_TILE}px;
  left: -${DRIFT_TILE}px;
  width: calc(100vw + ${DRIFT_TILE}px);
  height: calc(100vh + ${DRIFT_TILE}px);
  background-image:
    ${starDust};
  background-size: ${DRIFT_TILE}px ${DRIFT_TILE}px;
  animation: lux-drift 260s linear infinite;
  will-change: transform;
}

/* Two sparse layers of brighter stars fading out of phase. */
${DARK}::after,
${DARK_LOGO}::before {
  inset: 0;
}

${DARK}::after {
  background-image:
    ${twinkleA};
  background-size: ${TWINKLE_A_TILE}px ${TWINKLE_A_TILE}px;
  animation: lux-twinkle 4.2s ease-in-out infinite alternate;
}

${DARK_LOGO}::before {
  background-image:
    ${twinkleB};
  background-size: ${TWINKLE_B_TILE}px ${TWINKLE_B_TILE}px;
  animation: lux-twinkle 6.1s ease-in-out -2.4s infinite alternate;
}

/* Planet horizon: a huge dark sphere whose top edge is lit by a thin atmosphere. */
${DARK} > main::before {
  --planet: max(170vw, 1600px);
  top: 76vh;
  left: calc(50vw - var(--planet) / 2);
  width: var(--planet);
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 0%, #0a1230 0%, #04060f 16%, #000 38%);
  box-shadow:
    inset 0 2px 1px rgba(205, 225, 255, 0.6),
    inset 0 22px 44px -14px rgba(110, 150, 255, 0.4),
    0 -1px 6px rgba(175, 205, 255, 0.55),
    0 -14px 50px rgba(95, 120, 255, 0.32),
    0 -60px 160px rgba(120, 70, 210, 0.22);
  animation: lux-rise 40s ease-in-out infinite alternate;
}

/* Sunrise flare cresting the horizon, behind the card. */
${DARK} > main::after {
  top: 76vh;
  left: 50vw;
  width: min(900px, 120vw);
  height: 180px;
  transform: translate(-50%, -50%);
  background:
    linear-gradient(90deg, transparent, rgba(185, 210, 255, 0.5), transparent) center / 100% 1px no-repeat,
    radial-gradient(ellipse closest-side, rgba(255, 255, 255, 0.95) 0%, rgba(200, 215, 255, 0.55) 10%, rgba(130, 120, 255, 0.18) 38%, transparent 70%);
  mix-blend-mode: screen;
  animation: lux-flare 9s ease-in-out infinite alternate;
}

/* A faint, rare shooting star. */
${DARK_LOGO}::after {
  top: 16%;
  left: 70%;
  width: 180px;
  height: 1px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.9), rgba(170, 195, 255, 0.3) 45%, transparent);
  opacity: 0;
  transform: rotate(-22deg) translateX(0);
  animation: lux-meteor 14s ease-in 4s infinite;
}

${DARK_LOGO} img {
  filter: drop-shadow(0 0 28px rgba(170, 120, 255, 0.35)) drop-shadow(0 10px 24px rgba(0, 0, 0, 0.7));
}

/* Light theme paints inputs with a hard-coded white inset shadow (.webkit-dark-styles in
   client/src/style.css); on black, mirror its .dark variant. */
${DARK} .webkit-dark-styles,
${DARK} .webkit-dark-styles:focus {
  -webkit-text-fill-color: #fff;
  background-clip: content-box;
  -webkit-box-shadow: 0 0 0 50vh #0b0a10 inset;
}

${DARK} > main > div {
  background:
    linear-gradient(rgba(10, 9, 16, 0.74), rgba(10, 9, 16, 0.74)) padding-box,
    linear-gradient(140deg, rgba(180, 140, 255, 0.55), rgba(255, 255, 255, 0.06) 35%, rgba(255, 255, 255, 0.04) 65%, rgba(201, 164, 92, 0.45)) border-box;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 40px 100px -30px rgba(0, 0, 0, 0.95),
    0 0 90px -20px rgba(120, 80, 220, 0.35);
}

/* ========================= Light: above the clouds ========================= */

${LIGHT} {
  --sun-x: 76vw;
  --sun-y: 57vh;
  --accent-primary: 111 60 170;
  --accent-primary-hover: 91 44 131;
  color-scheme: light;
  background:
    linear-gradient(to top, rgba(252, 246, 243, 1) 0%, rgba(252, 246, 243, 0) 20%),
    radial-gradient(ellipse 45% 32% at 76% 58%, rgba(255, 226, 184, 0.9), transparent 72%),
    linear-gradient(180deg, #6fa3dc 0%, #9cc3ec 24%, #cfe0f2 46%, #efe3ea 64%, #f9dcc8 80%, #fbe9dc 100%);
}

/* Slow, soft light rays fanning out from the sun. */
${LIGHT}::before {
  top: var(--sun-y);
  left: var(--sun-x);
  width: 170vmax;
  aspect-ratio: 1;
  transform: translate(-50%, -50%) rotate(0deg);
  background: repeating-conic-gradient(rgba(255, 244, 222, 0.13) 0deg 3deg, transparent 3deg 11deg);
  -webkit-mask-image: radial-gradient(circle closest-side, #000 3%, rgba(0, 0, 0, 0.3) 22%, transparent 48%);
  mask-image: radial-gradient(circle closest-side, #000 3%, rgba(0, 0, 0, 0.3) 22%, transparent 48%);
  animation: lux-rays 36s ease-in-out infinite alternate;
}

/* The sun, low on the horizon with a wide bloom. */
${LIGHT}::after {
  top: var(--sun-y);
  left: var(--sun-x);
  width: clamp(90px, 8vw, 140px);
  aspect-ratio: 1;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, #fffdf6 0%, #fff4d8 45%, #ffe2a6 72%, #ffcf88 100%);
  box-shadow:
    0 0 30px 10px rgba(255, 244, 220, 0.9),
    0 0 120px 60px rgba(255, 216, 165, 0.55),
    0 0 320px 150px rgba(255, 200, 150, 0.28);
  animation: lux-sun 7s ease-in-out infinite alternate;
}

/* Sea of clouds: a hazy back layer and a brighter, faster front layer. */
${LIGHT} > main::before {${bottomScroller(CLOUD_BACK, '48vh')}
  background-image:
    ${cloudsBack};
  filter: blur(7px);
  opacity: 0.92;
  animation: lux-cloud-back 280s linear infinite;
}

${LIGHT} > main::after {${bottomScroller(CLOUD_FRONT, '40vh')}
  background-image:
    ${cloudsFront};
  filter: blur(2.5px) drop-shadow(0 -8px 22px rgba(255, 214, 170, 0.4));
  animation: lux-cloud-front 170s linear infinite;
}

/* High, thin cirrus. */
${LIGHT_LOGO}::before {
  top: 0;
  left: -${WISP.tile}px;
  width: calc(100vw + ${WISP.tile}px);
  height: 55vh;
  background-image:
    ${cirrus};
  background-size: ${WISP.tile}px ${WISP.height}px;
  background-repeat: repeat-x;
  filter: blur(10px);
  opacity: 0.7;
  animation: lux-cirrus 420s linear infinite;
  will-change: transform;
}

${LIGHT_LOGO}::after {
  display: none;
}

${LIGHT_LOGO} img {
  filter: drop-shadow(0 12px 26px rgba(80, 50, 140, 0.28));
}

${LIGHT} > main > div {
  background:
    linear-gradient(rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0.5)) padding-box,
    linear-gradient(140deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.35) 40%, rgba(190, 160, 230, 0.65)) border-box;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 40px 90px -30px rgba(70, 50, 130, 0.45),
    0 12px 30px -12px rgba(255, 170, 120, 0.3);
}

/* =============================== Motion =============================== */

@keyframes lux-drift {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(${DRIFT_TILE}px, ${DRIFT_TILE}px, 0); }
}

@keyframes lux-twinkle {
  from { opacity: 0.2; }
  to { opacity: 1; }
}

@keyframes lux-rise {
  from { transform: translateY(0); }
  to { transform: translateY(-8px); }
}

@keyframes lux-flare {
  from { opacity: 0.7; }
  to { opacity: 1; }
}

@keyframes lux-meteor {
  0% { opacity: 0; transform: rotate(-22deg) translateX(0); }
  2% { opacity: 1; }
  8% { opacity: 0; transform: rotate(-22deg) translateX(-560px); }
  100% { opacity: 0; transform: rotate(-22deg) translateX(-560px); }
}

@keyframes lux-rays {
  from { transform: translate(-50%, -50%) rotate(-4deg); }
  to { transform: translate(-50%, -50%) rotate(4deg); }
}

@keyframes lux-sun {
  from { transform: translate(-50%, -50%) scale(1); }
  to { transform: translate(-50%, -50%) scale(1.04); }
}

@keyframes lux-cloud-back {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(${CLOUD_BACK.tile}px, 0, 0); }
}

@keyframes lux-cloud-front {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(${CLOUD_FRONT.tile}px, 0, 0); }
}

@keyframes lux-cirrus {
  from { transform: translate3d(0, 0, 0); }
  to { transform: translate3d(${WISP.tile}px, 0, 0); }
}

@media (prefers-reduced-motion: reduce) {
  ${AUTH}::before,
  ${AUTH}::after,
  ${AUTH} > main::before,
  ${AUTH} > main::after,
  ${LOGO}::before {
    animation: none;
  }
  ${LOGO}::after {
    display: none;
  }
  ${BUTTON},
  ${BUTTON}:hover {
    transition: none;
    transform: none;
  }
}
`;

fs.writeFileSync(path.join(__dirname, 'space.css'), css);
console.log(`space.css written (${css.length} bytes)`);
