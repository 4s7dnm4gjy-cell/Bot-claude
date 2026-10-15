// Génère les visuels de vente : node visuals.mjs (nécessite Playwright, voir build.mjs).
// Sortie : visuals/product-*.png (2000×2000) et visuals/pin-*.png (1000×1500).
import { CHAPTERS } from './prompts.js';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, 'visuals');
mkdirSync(out, { recursive: true });
const { chromium } = await import(process.env.PLAYWRIGHT || 'playwright');

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const mark = s => esc(s).replace(/\[([^\]]+)\]/g, '<span class="ph">[$1]</span>');
const total = CHAPTERS.reduce((n, c) => n + c.prompts.length, 0);

const base = `
* { box-sizing: border-box; margin: 0; }
body { font-family: "Helvetica Neue", Arial, sans-serif; color: #1c1c1a; }
.frame { width: 100%; height: 100%; position: relative; overflow: hidden; background: #f7f6f2; display: flex; flex-direction: column; justify-content: center; }
.frame > .footer, .frame > div[style*='inset'], .frame > div[style*='width:36px'] { position: absolute; }
.accent { color: #d9480f; }
.kicker { color: #d9480f; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.lane { position: absolute; left: 0; right: 0; border-top: 3px solid #e2ddd0; }
.ph { background: #fff1ea; color: #b23c0c; border-radius: 6px; padding: 0 6px; }
.card { background: #fff; border: 2px solid #e2e0d8; border-radius: 24px; }
.footer { position: absolute; bottom: 0; left: 0; right: 0; background: #1c1c1a; color: #f7f6f2; font-weight: 700; }
`;
// Lignes de couloir de piste en fond.
const lanes = n => Array.from({ length: n }, (_, i) => `<div class="lane" style="top:${(i + 1) * (100 / (n + 1))}%"></div>`).join('');

function productCover() {
  return `<div class="frame" style="padding:150px 140px">
    <div style="position:absolute;inset:0;opacity:.6">${lanes(8)}</div>
    <div style="position:absolute;left:0;top:0;bottom:0;width:36px;background:#d9480f"></div>
    <div style="position:relative">
      <div class="kicker" style="font-size:44px">TrackPlan Coach Pack</div>
      <h1 style="font-size:190px;line-height:.98;letter-spacing:-.04em;margin:60px 0 50px">${total}<br>Lessons<br><span class="accent">for Track &amp; Field Coaches</span></h1>
      <p style="font-size:56px;color:#55534d;max-width:1500px">Ready-to-use AI prompts for season plans, sessions, meets &amp; club admin.</p>
    </div>
    <div class="footer" style="font-size:52px;padding:44px 140px">Instant PDF download · 23 pages · 10 chapters</div>
  </div>`;
}

function productContents() {
  return `<div class="frame" style="padding:130px 140px">
    <div class="kicker" style="font-size:44px">What's inside</div>
    <h2 style="font-size:110px;letter-spacing:-.03em;margin:30px 0 70px">10 chapters, 15 prompts each</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:44px 60px">
      ${CHAPTERS.map((c, i) => `<div style="font-size:62px;display:flex;gap:28px;align-items:baseline"><span class="accent" style="font-weight:800">${String(i + 1).padStart(2, '0')}</span><span>${esc(c.title)}</span></div>`).join('')}
    </div>
  </div>`;
}

function productExample() {
  const [t, p] = CHAPTERS[0].prompts[0];
  return `<div class="frame" style="padding:130px 140px">
    <div class="kicker" style="font-size:44px">How it works</div>
    <h2 style="font-size:110px;letter-spacing:-.03em;margin:30px 0 60px">Fill in the <span class="ph">[brackets]</span>. Paste. Done.</h2>
    <div class="card" style="padding:70px">
      <div style="font-size:60px;font-weight:800;margin-bottom:34px"><span class="accent">#1</span> ${esc(t)}</div>
      <div style="font-size:54px;line-height:1.5">${mark(p)}</div>
    </div>
    <p style="font-size:48px;color:#55534d;margin-top:60px">Works with ChatGPT, Claude, Gemini and Copilot, including free versions.</p>
  </div>`;
}

// Une épingle par chapitre : le titre du chapitre + un prompt concret.
function pin(ci) {
  const c = CHAPTERS[ci];
  const [t, p] = c.prompts[ci % c.prompts.length];
  return `<div class="frame" style="padding:80px 70px 170px">
    <div class="kicker" style="font-size:28px">AI prompt for coaches · ${String(ci + 1).padStart(2, '0')}</div>
    <h1 style="font-size:96px;line-height:1.02;letter-spacing:-.03em;margin:30px 0 50px">${esc(c.title)}</h1>
    <div class="card" style="padding:50px">
      <div style="font-size:42px;font-weight:800;margin-bottom:28px">${esc(t)}</div>
      <div style="font-size:37px;line-height:1.5">${mark(p)}</div>
    </div>
    <p style="font-size:32px;color:#55534d;margin-top:40px">Copy it, fill in the brackets, paste it into ChatGPT.</p>
    <div class="footer" style="font-size:34px;padding:34px 70px">150 Lessons for Track &amp; Field Coaches →</div>
  </div>`;
}

const browser = await chromium.launch();
async function shoot(html, w, h, file) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${base} html,body{width:${w}px;height:${h}px}</style></head><body>${html}</body></html>`);
  // Vérifie qu'aucun contenu ne dépasse du cadre.
  const overflow = await page.$eval('.frame', f => f.scrollHeight > f.clientHeight + 1 || f.scrollWidth > f.clientWidth + 1);
  if (overflow) console.warn(`Attention : contenu coupé dans ${file}`);
  await page.screenshot({ path: join(out, file) });
  await page.close();
}

await shoot(productCover(), 2000, 2000, 'product-1-cover.png');
await shoot(productContents(), 2000, 2000, 'product-2-contents.png');
await shoot(productExample(), 2000, 2000, 'product-3-example.png');
for (let i = 0; i < CHAPTERS.length; i++) await shoot(pin(i), 1000, 1500, `pin-${String(i + 1).padStart(2, '0')}.png`);
await browser.close();
console.log('Visuels générés dans', out);
