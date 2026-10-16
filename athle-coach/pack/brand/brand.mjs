// Charte TrackPlan partagée par le PDF et les visuels de vente.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const b64 = p => readFileSync(join(here, p)).toString('base64');

export const PHOTO = Object.fromEntries(
  ['portrait', 'race', 'start', 'bound', 'squat', 'park-set', 'park-drive']
    .map(n => [n, `data:image/jpeg;base64,${b64(`photos/${n}.jpg`)}`]),
);

// Photo d'ouverture de chaque chapitre (même ordre que CHAPTERS).
export const CHAPTER_PHOTO = ['race', 'start', 'bound', 'bound', 'squat', 'park-set', 'portrait', 'race', 'portrait', 'park-drive'];
// Cadrage de chaque photo dans un bandeau large (position verticale).
export const FOCUS = { race: '60% 30%', start: 'center 30%', bound: '55% 55%', squat: 'center 45%', 'park-set': 'center 70%', portrait: 'center 25%', 'park-drive': 'center 40%' };

export const COLORS = { navy: '#0a1630', ink: '#111827', orange: '#ff5a1f', blue: '#2a4d8f', sand: '#f4f1ea', line: '#e3ded2' };

export const FONT_CSS = `
@font-face { font-family: "Anton"; src: url(data:font/woff2;base64,${b64('fonts/anton.woff2')}) format("woff2"); }
.display { font-family: "Anton", "Inter Display", sans-serif; text-transform: uppercase; letter-spacing: .01em; font-weight: 400; }
body { font-family: Arial, "Liberation Sans", "Helvetica Neue", sans-serif; }
`;

// Logo : trois couloirs inclinés + nom.
export const logo = (size = 28, color = '#fff') => `
<span style="display:inline-flex;align-items:center;gap:${size * 0.35}px">
  <svg width="${size * 1.1}" height="${size}" viewBox="0 0 22 20" aria-hidden="true">
    <path d="M2 20 L8 0 H11 L5 20Z" fill="${COLORS.orange}"/>
    <path d="M8 20 L14 0 H17 L11 20Z" fill="${color}"/>
    <path d="M14 20 L20 0 H23 L17 20Z" fill="${color}" opacity=".55"/>
  </svg>
  <span class="display" style="font-size:${size}px;color:${color};line-height:1">Track<span style="color:${COLORS.orange}">Plan</span></span>
</span>`;

// Bandes de couloirs (motif de fond).
export const lanes = (opacity = 0.12, color = '#fff') =>
  `<div style="position:absolute;inset:0;background:repeating-linear-gradient(115deg, transparent 0 46px, rgba(255,255,255,${opacity}) 46px 49px);pointer-events:none;${color !== '#fff' ? `filter:invert(1)` : ''}"></div>`;
