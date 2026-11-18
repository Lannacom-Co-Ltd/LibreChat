/**
 * Brand logos for the model menu (modelSpecs iconURL), written to branding/models/*.svg and
 * served at /assets/custom/models/*.svg. Source: lobe-icons (MIT), pinned version, downloaded
 * once so the menu does not depend on a CDN.
 *
 * Single-colour logos (OpenAI, xAI, Kimi) use currentColor, which an <img> draws black and the
 * dark theme would hide, so they are placed on a small white disc that reads in both themes.
 *
 * Run: node branding/build-model-icons.js
 */
const fs = require('fs');
const path = require('path');

const VERSION = '1.103.0';
const SOURCE = `https://unpkg.com/@lobehub/icons-static-svg@${VERSION}/icons`;
const OUT = path.join(__dirname, 'models');
const INK = '#141413';

/** file name -> [lobe-icons name, needs a disc] */
const ICONS = {
  anthropic: ['claude-color', false],
  openai: ['openai', true],
  gemini: ['gemini-color', false],
  gemma: ['gemma-color', false],
  xai: ['grok', true],
  meta: ['meta-color', false],
  deepseek: ['deepseek-color', false],
  mistral: ['mistral-color', false],
  qwen: ['qwen-color', false],
  kimi: ['kimi-color', true],
  zhipu: ['zhipu-color', false],
  minimax: ['minimax-color', false],
  perplexity: ['perplexity-color', false],
};

function onDisc(svg) {
  const inner = svg
    .replace(/currentColor/g, INK)
    .replace(/<svg\b([^>]*)>/, (_, attrs) => {
      const kept = attrs.replace(/\s(width|height|x|y|style|class)="[^"]*"/g, '');
      return `<svg${kept} x="4.5" y="4.5" width="15" height="15">`;
    });
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">' +
    '<circle cx="12" cy="12" r="11.5" fill="#ffffff" stroke="#d9d7cf"/>' +
    inner +
    '</svg>'
  );
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  for (const [file, [name, disc]] of Object.entries(ICONS)) {
    const res = await fetch(`${SOURCE}/${name}.svg`);
    if (!res.ok) {
      throw new Error(`${name}: HTTP ${res.status}`);
    }
    const svg = (await res.text()).trim();
    if (!svg.startsWith('<svg')) {
      throw new Error(`${name}: not an SVG`);
    }
    fs.writeFileSync(path.join(OUT, `${file}.svg`), disc ? onDisc(svg) : svg);
    console.log(`models/${file}.svg <- ${name}${disc ? ' (on disc)' : ''}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
