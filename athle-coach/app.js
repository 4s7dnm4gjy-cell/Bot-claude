import { buildPlan, GROUP_NAMES } from './plans.js';
import { parseTime, formatTime, splits, predict, pacePerKm } from './calc.js';

// Lien de la liste d'attente Premium (formulaire, page de vente…). Vide = bouton masqué.
const WAITLIST_URL = '';

const T = {
  fr: {
    heroTitle: 'Ton plan d\'athlétisme, gratuit, en 10 secondes',
    heroSub: 'Sprint, 400 m, demi-fond, fond ou sauts : un plan périodisé jusqu\'à ta compétition, plus tes temps de passage.',
    tabPlan: 'Plan', tabSplits: 'Temps de passage', tabPredict: 'Prédiction',
    event: 'Discipline', weeks: 'Semaines avant la compétition', perWeek: 'Séances par semaine', level: 'Niveau',
    beginner: 'Débutant', advanced: 'Confirmé', generate: 'Générer mon plan', compute: 'Calculer',
    distance: 'Distance (m)', target: 'Temps visé', every: 'Passage tous les',
    knownDist: 'Distance connue (m)', knownTime: 'Ton temps',
    week: 'Semaine', deload: 'semaine allégée', print: 'Imprimer / PDF',
    at: 'À', time: 'Temps', pace: 'Allure /km', predicted: 'Temps estimé',
    badTime: 'Temps invalide. Exemple : 4:30 ou 58.20',
    riegelNote: 'Estimation par la formule de Riegel, fiable du 800 m au 10 km si tu es entraîné pour la distance visée.',
    premiumTitle: 'Bientôt : TrackPlan Premium',
    premiumText: 'Un coach IA qui adapte ton plan chaque semaine à tes chronos, ta fatigue et ton calendrier, et analyse ta vidéo de course.',
    premiumCta: 'Rejoindre la liste d\'attente',
    disclaimer: 'Plans indicatifs, pas un avis médical. En cas de douleur, arrête et consulte. Adapte avec ton entraîneur.',
  },
  en: {
    heroTitle: 'Your track & field plan, free, in 10 seconds',
    heroSub: 'Sprint, 400m, middle distance, long distance or jumps: a periodized plan up to your meet, plus your splits.',
    tabPlan: 'Plan', tabSplits: 'Splits', tabPredict: 'Predictor',
    event: 'Event group', weeks: 'Weeks until the meet', perWeek: 'Sessions per week', level: 'Level',
    beginner: 'Beginner', advanced: 'Advanced', generate: 'Build my plan', compute: 'Calculate',
    distance: 'Distance (m)', target: 'Target time', every: 'Split every',
    knownDist: 'Known distance (m)', knownTime: 'Your time',
    week: 'Week', deload: 'recovery week', print: 'Print / PDF',
    at: 'At', time: 'Time', pace: 'Pace /km', predicted: 'Predicted time',
    badTime: 'Invalid time. Example: 4:30 or 58.20',
    riegelNote: 'Estimate from Riegel\'s formula, reliable from 800m to 10k if you are trained for the target distance.',
    premiumTitle: 'Coming soon: TrackPlan Premium',
    premiumText: 'An AI coach that adapts your plan every week to your times, fatigue and schedule, and analyzes your race video.',
    premiumCta: 'Join the waitlist',
    disclaimer: 'Guidance only, not medical advice. Stop and see a professional if something hurts. Adapt with your coach.',
  },
};

let lang = (() => {
  try { return localStorage.getItem('lang') || (navigator.language.startsWith('fr') ? 'fr' : 'en'); } catch { return 'fr'; }
})();
const $ = sel => document.querySelector(sel);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = T[lang][el.dataset.i18n]; });
  $('#lang').textContent = lang === 'fr' ? 'EN' : 'FR';
  const sel = $('#groupSelect');
  const current = sel.value || 'middle';
  sel.innerHTML = Object.entries(GROUP_NAMES).map(([k, v]) => `<option value="${k}">${esc(v[lang])}</option>`).join('');
  sel.value = current;
  const wl = $('#waitlist');
  wl.hidden = !WAITLIST_URL;
  if (WAITLIST_URL) wl.href = WAITLIST_URL;
  if ($('#planOut').innerHTML) renderPlan();
}

function renderPlan() {
  const f = new FormData($('#planForm'));
  const weeks = Math.min(24, Math.max(2, Number(f.get('weeks')) || 10));
  const plan = buildPlan({ group: f.get('group'), weeks, perWeek: Number(f.get('perWeek')), level: f.get('level'), lang });
  const t = T[lang];
  $('#planOut').innerHTML = `<button type="button" class="ghost print" onclick="window.print()">${t.print}</button>` +
    plan.map(w => `
      <article class="week phase-${w.phase}">
        <h3>${t.week} ${w.week} · ${esc(w.phaseName)}${w.deload ? ` <span class="tag">${t.deload}</span>` : ''}</h3>
        <ul>${w.sessions.map(s => `<li><b>${esc(s.day)}</b> <span class="title">${esc(s.title)}</span><span class="detail">${esc(s.detail)}</span></li>`).join('')}</ul>
      </article>`).join('');
}

function renderSplits() {
  const f = new FormData($('#splitForm'));
  const dist = Number(f.get('distance'));
  const sec = parseTime(f.get('time'));
  const t = T[lang];
  if (!(sec > 0)) { $('#splitOut').innerHTML = `<p class="error">${t.badTime}</p>`; return; }
  const step = Math.min(Number(f.get('step')), dist);
  const rows = splits(dist, sec, step);
  $('#splitOut').innerHTML = `<table><thead><tr><th>${t.at}</th><th>${t.time}</th></tr></thead><tbody>` +
    rows.map(r => `<tr><td>${r.at} m</td><td>${formatTime(r.time)}</td></tr>`).join('') +
    `</tbody></table><p class="note">${t.pace} : ${formatTime(pacePerKm(dist, sec), 1)}</p>`;
}

function renderPredict() {
  const f = new FormData($('#predForm'));
  const from = Number(f.get('from'));
  const sec = parseTime(f.get('time'));
  const t = T[lang];
  if (!(sec > 0)) { $('#predOut').innerHTML = `<p class="error">${t.badTime}</p>`; return; }
  const targets = [800, 1500, 3000, 5000, 10000].filter(d => d !== from);
  $('#predOut').innerHTML = `<table><thead><tr><th>Distance</th><th>${t.predicted}</th><th>${t.pace}</th></tr></thead><tbody>` +
    targets.map(d => { const p = predict(from, sec, d); return `<tr><td>${d} m</td><td>${formatTime(p, 1)}</td><td>${formatTime(pacePerKm(d, p), 0)}</td></tr>`; }).join('') +
    '</tbody></table>';
}

document.querySelectorAll('.tabs button').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tabs button, .panel').forEach(el => el.classList.remove('active'));
  btn.classList.add('active');
  $(`#${btn.dataset.tab}`).classList.add('active');
}));
$('#lang').addEventListener('click', () => {
  lang = lang === 'fr' ? 'en' : 'fr';
  try { localStorage.setItem('lang', lang); } catch { /* stockage indisponible */ }
  applyLang();
});
$('#planForm').addEventListener('submit', e => { e.preventDefault(); renderPlan(); });
$('#splitForm').addEventListener('submit', e => { e.preventDefault(); renderSplits(); });
$('#predForm').addEventListener('submit', e => { e.preventDefault(); renderPredict(); });

applyLang();
