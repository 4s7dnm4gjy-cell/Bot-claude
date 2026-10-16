// Génère les visuels de vente : node visuals.mjs (nécessite Playwright, voir build.mjs).
// Sortie : visuals/product-*.png (2000×2000) et visuals/pin-*.png (1000×1500).
import { CHAPTERS } from './prompts.js';
import { PHOTO, CHAPTER_PHOTO, FOCUS, COLORS as C, FONT_CSS, logo } from './brand/brand.mjs';
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
const pad = i => String(i).padStart(2, '0');

const base = `
${FONT_CSS}
* { box-sizing: border-box; margin: 0; }
body { color: ${C.ink}; }
.frame { width: 100%; height: 100%; position: relative; overflow: hidden; background: ${C.navy}; color: #fff; }
.bg { position: absolute; inset: 0; background-size: cover; background-repeat: no-repeat; }
.accent { color: ${C.orange}; }
.kicker { color: ${C.orange}; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.ph { background: #ffe9df; color: #c2410c; border-radius: 6px; padding: 0 6px; font-weight: 600; }
.card { background: #fff; color: ${C.ink}; border-radius: 22px; border-left: 10px solid ${C.orange}; }
.strip { position: absolute; left: 0; right: 0; bottom: 0; background: ${C.orange}; color: ${C.navy}; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; display: flex; justify-content: space-between; align-items: center; }
.stripes { position: absolute; background: repeating-linear-gradient(115deg, transparent 0 34px, ${C.orange} 34px 44px); }
`;

function productCover() {
  return `<div class="frame">
    <div class="bg" style="background-image:linear-gradient(180deg, rgba(10,22,48,.15) 0%, rgba(10,22,48,.3) 35%, rgba(10,22,48,.97) 68%), url(${PHOTO.bound}); background-position:55% 40%"></div>
    <div style="position:absolute;top:110px;left:130px;right:130px;display:flex;justify-content:space-between;align-items:center">${logo(80)}<span style="border:4px solid rgba(255,255,255,.75);border-radius:99px;padding:18px 44px;font-size:36px;font-weight:800;letter-spacing:.14em">COACH PACK</span></div>
    <div style="position:absolute;left:130px;right:130px;bottom:260px">
      <div class="kicker" style="font-size:44px">Written by a competing athlete</div>
      <h1 class="display" style="font-size:230px;line-height:.92;margin:36px 0 40px">${total} Lessons<br>for <span class="accent">Track &amp; Field</span><br>Coaches</h1>
      <p style="font-size:56px;color:#dbe3f0;max-width:1600px">Ready-to-use AI prompts for plans, sessions, meets and club admin.</p>
    </div>
    <div class="strip" style="height:140px;padding:0 130px;font-size:44px"><span>10 chapters</span><span>Instant PDF</span><span>Any AI assistant</span></div>
  </div>`;
}

function productContents() {
  return `<div class="frame" style="display:grid;grid-template-columns:44% 56%">
    <div style="position:relative">
      <div class="bg" style="background-image:url(${PHOTO.portrait});background-position:center 25%"></div>
      <div class="stripes" style="right:-40px;top:0;bottom:0;width:120px"></div>
    </div>
    <div style="padding:120px 110px 0 130px">
      <div class="kicker" style="font-size:40px">What's inside</div>
      <h2 class="display" style="font-size:110px;line-height:1;margin:20px 0 40px">10 chapters,<br>15 prompts each</h2>
      ${CHAPTERS.map((c, i) => `<div style="display:flex;gap:32px;align-items:baseline;padding:17px 0;border-bottom:2px solid rgba(255,255,255,.12)"><span class="display accent" style="font-size:52px;width:80px;flex:none">${pad(i + 1)}</span><span style="font-size:40px;font-weight:600">${esc(c.title)}</span></div>`).join('')}
    </div>
  </div>`;
}

function productExample() {
  const [t, p] = CHAPTERS[0].prompts[0];
  return `<div class="frame" style="background:${C.sand};color:${C.ink}">
    <div class="bg" style="left:auto;width:38%;background-image:url(${PHOTO['park-set']});background-position:center 60%"></div>
    <div class="stripes" style="left:calc(62% - 100px);top:0;bottom:0;width:100px"></div>
    <div style="position:absolute;left:120px;top:140px;width:1000px">
      <div class="kicker" style="font-size:40px">How it works</div>
      <h2 class="display" style="font-size:118px;line-height:1;color:${C.navy};margin:24px 0 60px">Fill in the brackets.<br>Paste. <span class="accent">Coach.</span></h2>
      <div class="card" style="padding:64px 70px;box-shadow:0 30px 80px rgba(10,22,48,.18)">
        <div style="font-size:50px;font-weight:800;margin-bottom:26px;color:${C.navy}"><span class="display accent" style="margin-right:22px">01</span>${esc(t)}</div>
        <div style="font-size:38px;line-height:1.5">${mark(p)}</div>
      </div>
      <p style="font-size:42px;color:#4b5563;margin-top:56px">Works with ChatGPT, Claude, Gemini and Copilot, free versions included.</p>
    </div>
  </div>`;
}

// Une épingle par chapitre : photo, titre du chapitre et un vrai prompt.
function pin(ci) {
  const c = CHAPTERS[ci];
  const [t, p] = c.prompts[ci % c.prompts.length];
  const ph = CHAPTER_PHOTO[ci];
  return `<div class="frame">
    <div class="bg" style="height:46%;background-image:linear-gradient(180deg, rgba(10,22,48,.1) 40%, ${C.navy} 100%), url(${PHOTO[ph]});background-position:${FOCUS[ph]}"></div>
    <div style="position:absolute;top:50px;left:60px">${logo(46)}</div>
    <div style="position:absolute;left:60px;right:60px;top:440px">
      <div class="kicker" style="font-size:26px">Free AI prompt for coaches · ${pad(ci + 1)}</div>
      <h1 class="display" style="font-size:92px;line-height:.98;margin:18px 0 36px">${esc(c.title)}</h1>
      <div class="card" style="padding:40px 44px">
        <div style="font-size:36px;font-weight:800;margin-bottom:20px;color:${C.navy}">${esc(t)}</div>
        <div style="font-size:30px;line-height:1.5">${mark(p)}</div>
      </div>
    </div>
    <div class="strip" style="height:100px;padding:0 60px;font-size:30px"><span>${total} Lessons for Track &amp; Field Coaches</span><span>→</span></div>
  </div>`;
}

const browser = await chromium.launch();
async function shoot(html, w, h, file) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${base} html,body{width:${w}px;height:${h}px}</style></head><body>${html}</body></html>`);
  await page.evaluate(() => document.fonts.ready);
  // Signale un contenu qui dépasse le bas du cadre (au-dessus du bandeau).
  const over = await page.evaluate(() => {
    const strip = document.querySelector('.strip');
    const limit = strip ? strip.getBoundingClientRect().top : innerHeight;
    return [...document.querySelectorAll('.card, h1, h2, p')].some(e => e.getBoundingClientRect().bottom > limit + 1);
  });
  if (over) console.warn(`Attention : contenu trop long dans ${file}`);
  await page.screenshot({ path: join(out, file) });
  await page.close();
}

await shoot(productCover(), 2000, 2000, 'product-1-cover.png');
await shoot(productContents(), 2000, 2000, 'product-2-contents.png');
await shoot(productExample(), 2000, 2000, 'product-3-example.png');
for (let i = 0; i < CHAPTERS.length; i++) await shoot(pin(i), 1000, 1500, `pin-${pad(i + 1)}.png`);
await browser.close();
console.log('Visuels générés dans', out);
