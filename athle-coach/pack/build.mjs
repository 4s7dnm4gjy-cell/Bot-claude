// Génère le PDF du pack : node build.mjs (nécessite Playwright).
// Usage : PLAYWRIGHT=/chemin/vers/playwright/index.mjs node build.mjs
import { CHAPTERS } from './prompts.js';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(process.env.PLAYWRIGHT || 'playwright');

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const mark = s => esc(s).replace(/\[([^\]]+)\]/g, '<span class="ph">[$1]</span>');
const total = CHAPTERS.reduce((n, c) => n + c.prompts.length, 0);

let n = 0;
const chapters = CHAPTERS.map((c, ci) => `
  <section class="chapter">
    <div class="chap-head"><span class="num">${String(ci + 1).padStart(2, '0')}</span><h2>${esc(c.title)}</h2></div>
    <p class="intro">${esc(c.intro)}</p>
    ${c.prompts.map(([t, p]) => `<div class="prompt"><h3><span>#${++n}</span> ${esc(t)}</h3><p>${mark(p)}</p></div>`).join('')}
  </section>`).join('');

const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.5 "Helvetica Neue", Arial, sans-serif; color: #1c1c1a; margin: 0; }
.cover { height: 257mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; border-left: 10px solid #d9480f; padding-left: 14mm; }
.cover .kicker { color: #d9480f; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: 10pt; }
.cover h1 { font-size: 40pt; line-height: 1.05; margin: 8mm 0 6mm; letter-spacing: -.02em; }
.cover p { font-size: 13pt; color: #55534d; max-width: 140mm; }
.page { page-break-after: always; }
h2 { font-size: 20pt; margin: 0; letter-spacing: -.01em; }
.howto h2 { margin-bottom: 4mm; }
.howto li { margin-bottom: 2mm; }
.toc li { display: flex; justify-content: space-between; border-bottom: 1px dotted #ccc; padding: 1.5mm 0; }
.chapter { page-break-before: always; }
.chap-head { display: flex; align-items: baseline; gap: 4mm; border-bottom: 2px solid #1c1c1a; padding-bottom: 2mm; }
.num { color: #d9480f; font-weight: 800; font-size: 20pt; }
.intro { color: #55534d; margin: 3mm 0 5mm; }
.prompt { break-inside: avoid; border: 1px solid #e2e0d8; border-radius: 6px; padding: 3mm 4mm; margin-bottom: 3mm; }
.prompt h3 { font-size: 10.5pt; margin: 0 0 1.5mm; }
.prompt h3 span { color: #d9480f; margin-right: 1mm; }
.prompt p { margin: 0; }
.ph { background: #fff1ea; color: #b23c0c; border-radius: 3px; padding: 0 2px; }
.note { font-size: 9pt; color: #55534d; }
</style></head><body>
<div class="cover">
  <div class="kicker">TrackPlan Coach Pack</div>
  <h1>${total} Lessons for<br>Track &amp; Field Coaches</h1>
  <p>Ready-to-use AI prompts for season plans, sessions for every event group, youth coaching, meet preparation and club admin. Copy, fill in the brackets, paste into ChatGPT, Claude or Gemini.</p>
</div>
<div class="page howto">
  <h2>How to use this pack</h2>
  <ol>
    <li><b>Pick a prompt</b> from the chapter that matches your task.</li>
    <li><b>Replace every <span class="ph">[bracket]</span></b> with your real details: ages, times, dates, facilities. The more specific you are, the better the answer.</li>
    <li><b>Paste it</b> into any AI assistant (ChatGPT, Claude, Gemini, Copilot).</li>
    <li><b>Follow up.</b> Ask "make it shorter", "adapt it for 14-year-olds" or "turn it into a table". The first answer is a draft, not the final plan.</li>
    <li><b>Apply your judgement.</b> You know your athletes; the AI does not. Check every session against their level, health and history.</li>
  </ol>
  <p class="note"><b>Important:</b> AI output is general guidance, not medical advice. For injuries, pain, nutrition plans or health conditions, refer athletes to a qualified professional.</p>
  <h2 style="margin-top:10mm">Contents</h2>
  <ol class="toc">${CHAPTERS.map((c, i) => `<li><span>${String(i + 1).padStart(2, '0')}. ${esc(c.title)}</span><span>${c.prompts.length} prompts</span></li>`).join('')}</ol>
</div>
${chapters}
</body></html>`;

writeFileSync(join(here, 'pack.html'), html);
const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent(html, { waitUntil: 'load' });
await page.pdf({ path: join(here, '150-Lessons-for-Track-and-Field-Coaches.pdf'), format: 'A4', printBackground: true,
  displayHeaderFooter: true, headerTemplate: '<span></span>',
  footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#999">TrackPlan Coach Pack · <span class="pageNumber"></span></div>' });
await browser.close();
console.log(`PDF généré : ${total} prompts`);
