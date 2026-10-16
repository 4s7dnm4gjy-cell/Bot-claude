// Génère le PDF du pack : node build.mjs (nécessite Playwright).
// Usage : PLAYWRIGHT=/chemin/vers/playwright/index.mjs node build.mjs
import { CHAPTERS } from './prompts.js';
import { PHOTO, CHAPTER_PHOTO, FOCUS, COLORS as C, FONT_CSS, logo } from './brand/brand.mjs';
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const { chromium } = await import(process.env.PLAYWRIGHT || 'playwright');

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const mark = s => esc(s).replace(/\[([^\]]+)\]/g, '<span class="ph">[$1]</span>');
const total = CHAPTERS.reduce((n, c) => n + c.prompts.length, 0);
const pad = i => String(i).padStart(2, '0');

let n = 0;
const chapters = CHAPTERS.map((c, ci) => `
  <section class="chapter">
    <div class="opener">
      <div class="photo" style="background-image:linear-gradient(90deg, #0a1630 0%, rgba(10,22,48,0) 45%), url(${PHOTO[CHAPTER_PHOTO[ci]]}); background-position:${FOCUS[CHAPTER_PHOTO[ci]]}"></div>
      <div class="stripes"></div>
      <div class="num display">${pad(ci + 1)}</div>
      <h2 class="display">${esc(c.title)}</h2>
      <p>${esc(c.intro)}</p>
    </div>
    ${c.prompts.map(([t, p]) => `<div class="prompt"><h3><span class="display">${pad(++n)}</span>${esc(t)}</h3><p>${mark(p)}</p></div>`).join('')}
  </section>`).join('');

const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
${FONT_CSS}
@page { size: A4; margin: 16mm 15mm 18mm; }
* { box-sizing: border-box; }
body { font-size: 10pt; line-height: 1.45; color: ${C.ink}; margin: 0; }
.ph { background: #ffe9df; color: #c2410c; border-radius: 3px; padding: 0 2px; font-weight: 600; }

.cover { width: 210mm; height: 296mm; position: relative; color: #fff; overflow: hidden; page-break-after: always;
  background: linear-gradient(180deg, rgba(10,22,48,.25) 0%, rgba(10,22,48,.35) 40%, rgba(10,22,48,.96) 72%), url(${PHOTO.bound}) center 30% / cover; }
.cover .top { position: absolute; top: 16mm; left: 16mm; right: 16mm; display: flex; justify-content: space-between; align-items: center; }
.cover .badge { border: 1.5px solid rgba(255,255,255,.7); border-radius: 99px; padding: 2mm 5mm; font-size: 9pt; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.cover .body { position: absolute; left: 16mm; right: 16mm; bottom: 30mm; }
.cover .kicker { color: ${C.orange}; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; font-size: 11pt; }
.cover h1 { font-size: 66pt; line-height: .95; margin: 5mm 0 6mm; }
.cover h1 .accent { color: ${C.orange}; }
.cover .sub { font-size: 13pt; color: #dbe3f0; max-width: 150mm; }
.cover .strip { position: absolute; left: 0; right: 0; bottom: 0; height: 14mm; background: ${C.orange}; display: flex; align-items: center; justify-content: space-between; padding: 0 16mm; font-weight: 800; font-size: 10pt; letter-spacing: .08em; text-transform: uppercase; color: ${C.navy}; }

.page { page-break-after: always; }
.about { display: grid; grid-template-columns: 62mm 1fr; gap: 9mm; align-items: start; }
.about img { width: 62mm; height: 88mm; object-fit: cover; border-radius: 4mm; }
.eyebrow { color: ${C.orange}; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; font-size: 8.5pt; }
h2.display { font-size: 26pt; line-height: 1; margin: 2mm 0 4mm; color: ${C.navy}; }
.steps { counter-reset: s; list-style: none; padding: 0; margin: 4mm 0; }
.steps li { counter-increment: s; position: relative; padding-left: 11mm; margin-bottom: 3mm; }
.steps li::before { content: counter(s); position: absolute; left: 0; top: -.5mm; width: 7mm; height: 7mm; border-radius: 50%; background: ${C.navy}; color: #fff; font-weight: 800; font-size: 9pt; display: flex; align-items: center; justify-content: center; }
.warn { border-left: 3px solid ${C.orange}; background: #fff6f1; padding: 3mm 4mm; font-size: 9pt; color: #44403c; border-radius: 0 2mm 2mm 0; }

.toc { list-style: none; padding: 0; margin: 4mm 0 0; }
.toc li { display: grid; grid-template-columns: 14mm 1fr auto; align-items: center; padding: 3.2mm 0; border-bottom: 1px solid ${C.line}; }
.toc .display { color: ${C.orange}; font-size: 18pt; }
.toc .t { font-weight: 700; font-size: 11pt; color: ${C.navy}; }
.toc .c { font-size: 9pt; color: #6b7280; }

.chapter { page-break-before: always; }
.opener { position: relative; height: 64mm; border-radius: 4mm; background: #0a1630; color: #fff; padding: 8mm 11mm; margin-bottom: 5mm; overflow: hidden; }
.opener .photo { position: absolute; right: 0; top: 0; bottom: 0; width: 42%; background-size: cover; background-repeat: no-repeat; }
.opener .stripes { position: absolute; left: 57%; top: 0; bottom: 0; width: 14mm; transform: translateX(-50%); background: repeating-linear-gradient(115deg, transparent 0 3.2mm, ${C.orange} 3.2mm 4.4mm); opacity: .9; }
.opener > *:not(.photo):not(.stripes) { position: relative; }
.opener .num { color: ${C.orange}; font-size: 40pt; line-height: 1; }
.opener h2 { font-size: 26pt; line-height: 1; margin: 3mm 0 3mm; max-width: 84mm; color: #fff; }
.opener p { max-width: 80mm; color: #dbe3f0; margin: 0; font-size: 10.5pt; }

.prompt { break-inside: avoid; border: 1px solid ${C.line}; border-left: 3px solid ${C.orange}; border-radius: 0 2.5mm 2.5mm 0; padding: 2.6mm 4.5mm; margin-bottom: 2.4mm; background: #fff; }
.prompt h3 { font-size: 10.5pt; margin: 0 0 1.5mm; color: ${C.navy}; display: flex; gap: 2.5mm; align-items: baseline; }
.prompt h3 .display { color: ${C.orange}; font-size: 12pt; }
.prompt p { margin: 0; color: #1f2937; }

.final { page-break-before: always; background: ${C.navy}; color: #fff; border-radius: 4mm; padding: 16mm 14mm; position: relative; overflow: hidden; }
.final h2 { color: #fff; font-size: 30pt; }
.final p { color: #dbe3f0; max-width: 140mm; }
</style></head><body>

<div class="cover">
  <div class="top">${logo(30)}<span class="badge">Coach Pack</span></div>
  <div class="body">
    <div class="kicker">Written by a competing athlete</div>
    <h1 class="display">${total} Lessons<br>for <span class="accent">Track &amp; Field</span><br>Coaches</h1>
    <p class="sub">Ready-to-use AI prompts for season plans, sessions for every event group, youth coaching, meet preparation and club admin.</p>
  </div>
  <div class="strip"><span>10 chapters</span><span>${total} prompts</span><span>Instant use with any AI</span></div>
</div>
<!--BODY-->

<div class="page">
  <div class="about">
    <img src="${PHOTO.portrait}" alt="The author at an indoor meet">
    <div>
      <div class="eyebrow">Why this pack exists</div>
      <h2 class="display">From the track, for coaches</h2>
      <p>I compete in athletics in Belgium. Every week I see coaches spend hours on plans, session ideas and messages to parents, time they would rather spend on the track.</p>
      <p>AI can do the heavy lifting, but only if you ask the right way. This pack gathers ${total} prompts written with real athletics in mind: periodization, block starts, approach runs, tapering, youth groups and the admin around a club.</p>
      <p>Fill in the brackets with your athletes' details, paste the prompt into any AI assistant and keep your coaching judgement in charge.</p>
    </div>
  </div>
  <div style="margin-top:9mm">
    <div class="eyebrow">How to use it</div>
    <h2 class="display">Four steps, two minutes</h2>
    <ol class="steps">
      <li><b>Pick a prompt</b> from the chapter that matches your task.</li>
      <li><b>Replace every <span class="ph">[bracket]</span></b> with real details: ages, times, dates, facilities. Specific input gives specific answers.</li>
      <li><b>Paste it</b> into ChatGPT, Claude, Gemini or Copilot. Free versions work.</li>
      <li><b>Refine it.</b> Ask "shorter", "for 14-year-olds" or "as a table". The first answer is a draft; you know your athletes, the AI does not.</li>
    </ol>
    <p class="warn"><b>Important:</b> AI output is general guidance, not medical advice. For injuries, pain, nutrition plans or health conditions, refer athletes to a qualified professional.</p>
  </div>
</div>

<div class="page">
  <div class="eyebrow">Contents</div>
  <h2 class="display">Ten chapters, every part of coaching</h2>
  <ol class="toc">${CHAPTERS.map((c, i) => `<li><span class="display">${pad(i + 1)}</span><span class="t">${esc(c.title)}</span><span class="c">${c.prompts.length} prompts</span></li>`).join('')}</ol>
</div>

${chapters}

<div class="final">
  ${logo(26)}
  <h2 class="display" style="margin-top:8mm">Keep the plan. Coach the athlete.</h2>
  <p>Thanks for coaching. If this pack saved you time, a short review helps a student athlete keep building tools for coaches.</p>
</div>
</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage();
const out = join(here, '150-Lessons-for-Track-and-Field-Coaches.pdf');
const coverPdf = join(here, '.cover.pdf'), bodyPdf = join(here, '.body.pdf');
const [head] = html.split('<!--BODY-->');
await page.setContent(head.replace('</head>', '<style>@page { margin: 0 }</style></head>') + '</body></html>', { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
await page.pdf({ path: coverPdf, format: 'A4', printBackground: true, pageRanges: '1' });
await page.setContent(html.replace(/<div class="cover">[\s\S]*?<!--BODY-->/, ''), { waitUntil: 'load' });
await page.evaluate(() => document.fonts.ready);
await page.pdf({ path: bodyPdf, format: 'A4', printBackground: true,
  displayHeaderFooter: true, headerTemplate: '<span></span>',
  footerTemplate: `<div style="font-size:7.5px;width:100%;padding:0 15mm;display:flex;justify-content:space-between;color:#9ca3af;font-family:Inter,Arial"><span>TRACKPLAN · 150 Lessons for Track &amp; Field Coaches</span><span class="pageNumber"></span></div>` });
await browser.close();
execFileSync('pdfunite', [coverPdf, bodyPdf, out]);
rmSync(coverPdf); rmSync(bodyPdf);
console.log(`PDF généré : ${total} prompts`);
