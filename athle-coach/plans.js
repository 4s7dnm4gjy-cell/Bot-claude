// Bibliothèque de séances et générateur de plan périodisé.
// Notation des volumes : {a|b} = a pour un débutant, b pour un athlète confirmé.

const PHASES = {
  G: { fr: 'Préparation générale', en: 'General preparation' },
  S: { fr: 'Préparation spécifique', en: 'Specific preparation' },
  C: { fr: 'Compétition', en: 'Competition' },
  A: { fr: 'Affûtage', en: 'Taper' },
};

const S = (frT, frD, enT, enD) => ({ fr: { t: frT, d: frD }, en: { t: enT, d: enD } });

const COMMON = {
  muscu: S('Renforcement', 'Squat {3|4}×{8|6}, fentes {3|3}×10, gainage 3×45 s, mollets 3×15',
    'Strength', 'Squat {3|4}×{8|6}, lunges {3|3}×10, core 3×45 s, calf raises 3×15'),
  muscuMax: S('Force max', 'Squat ou épaulé {3|5}×{5|3} à charge lourde, sauts de haies 4×5, gainage',
    'Max strength', 'Squat or power clean {3|5}×{5|3} heavy, hurdle hops 4×5, core'),
  recup: S('Récupération active', 'Footing 20 min très lent, mobilité 15 min, étirements',
    'Active recovery', 'Easy jog 20 min, mobility 15 min, stretching'),
  compet: S('Compétition', 'Échauffement complet, course ou concours. Noter le résultat et les sensations.',
    'Competition', 'Full warm-up, race or field event. Log the result and how it felt.'),
  preCompet: S('Veille de compétition', 'Échauffement, 3 lignes droites à 90 %, 2 départs. Rien de fatigant.',
    'Pre-competition', 'Warm-up, 3 strides at 90%, 2 starts. Nothing tiring.'),
};

const GROUPS = {
  sprint: {
    fr: 'Sprint (100 m, 200 m)', en: 'Sprint (100m, 200m)',
    G: [
      S('Technique et accélération', 'Gammes 20 min, {6|8}×30 m départ debout, récup 2 min', 'Drills and acceleration', 'Drills 20 min, {6|8}×30m standing start, 2 min rest'),
      COMMON.muscu,
      S('Endurance de vitesse', '{2|3} séries de 4×100 m à 75 %, récup 1 min / 5 min', 'Speed endurance', '{2|3} sets of 4×100m at 75%, 1 min / 5 min rest'),
      S('Pliométrie', 'Bonds alternés {4|6}×30 m, sauts à pieds joints {4|5}×5', 'Plyometrics', 'Bounding {4|6}×30m, standing jumps {4|5}×5'),
      COMMON.recup,
      S('Côtes', '{6|8}×60 m en côte légère, retour marché', 'Hills', '{6|8}×60m on a gentle hill, walk back'),
    ],
    S: [
      S('Départs en blocs', '{6|8}×30 m blocs, récup 3 min', 'Block starts', '{6|8}×30m from blocks, 3 min rest'),
      COMMON.muscuMax,
      S('Vitesse maximale', '{4|6}×30 m lancés (20 m d\'élan), récup 4 min', 'Max velocity', '{4|6}×30m flying (20m run-in), 4 min rest'),
      S('Endurance spécifique', '{3|4}×150 m à 90 %, récup 6 min', 'Specific endurance', '{3|4}×150m at 90%, 6 min rest'),
      COMMON.recup,
      S('Technique de virage', '{4|6}×80 m en virage à 85 %', 'Bend running', '{4|6}×80m on the bend at 85%'),
    ],
    C: [
      S('Vitesse courte', '{4|5}×40 m blocs à 100 %, récup complète', 'Short speed', '{4|5}×40m blocks at 100%, full rest'),
      COMMON.preCompet,
      COMMON.compet,
      S('Entretien', '{2|3}×120 m à 90 %, gainage', 'Maintenance', '{2|3}×120m at 90%, core'),
      COMMON.recup,
      COMMON.muscu,
    ],
  },
  quarter: {
    fr: '400 m', en: '400m',
    G: [
      S('Volume aérobie', '{4|6}×300 m à 70 %, récup 2 min', 'Aerobic volume', '{4|6}×300m at 70%, 2 min rest'),
      COMMON.muscu,
      S('Technique et vitesse', 'Gammes, {5|6}×60 m progressifs', 'Drills and speed', 'Drills, {5|6}×60m build-ups'),
      S('Côtes longues', '{6|8}×150 m en côte, retour trot', 'Long hills', '{6|8}×150m uphill, jog back'),
      COMMON.recup,
      S('Circuit', '{3|4} tours de 8 exercices de 30 s', 'Circuit', '{3|4} rounds of 8 exercises, 30 s each'),
    ],
    S: [
      S('Lactique', '{2|3}×300 m à 90 %, récup 10 min', 'Lactic', '{2|3}×300m at 90%, 10 min rest'),
      COMMON.muscuMax,
      S('Vitesse', '{4|5}×60 m blocs + 2×150 m à 95 %', 'Speed', '{4|5}×60m blocks + 2×150m at 95%'),
      S('Rythme de course', '{2|3}×(200 m + 200 m) à allure 400 m, récup 1 min / 8 min', 'Race pace', '{2|3}×(200m + 200m) at 400m pace, 1 min / 8 min rest'),
      COMMON.recup,
      S('Tempo', '{6|8}×200 m à 75 %, récup 1 min 30', 'Tempo', '{6|8}×200m at 75%, 90 s rest'),
    ],
    C: [
      S('Rappel d\'allure', '{1|2}×300 m à allure course, 3×60 m', 'Pace reminder', '{1|2}×300m at race pace, 3×60m'),
      COMMON.preCompet,
      COMMON.compet,
      S('Vitesse', '{3|4}×80 m à 95 %, récup complète', 'Speed', '{3|4}×80m at 95%, full rest'),
      COMMON.recup,
      COMMON.muscu,
    ],
  },
  middle: {
    fr: 'Demi-fond (800 m, 1 500 m)', en: 'Middle distance (800m, 1500m)',
    G: [
      S('Endurance fondamentale', 'Footing {35|50} min, 5 lignes droites', 'Easy run', 'Easy run {35|50} min, 5 strides'),
      S('VMA courte', '{2|3} séries de 8×200 m à 100 % VMA, récup 200 m trot', 'Short intervals', '{2|3} sets of 8×200m at vVO2max, 200m jog'),
      COMMON.muscu,
      S('Sortie longue', 'Footing {45|70} min vallonné', 'Long run', 'Hilly easy run {45|70} min'),
      S('Seuil', '{3|4}×{6|8} min à allure seuil, récup 2 min', 'Threshold', '{3|4}×{6|8} min at threshold, 2 min rest'),
      COMMON.recup,
    ],
    S: [
      S('Allure spécifique', '{4|6}×400 m à allure 1 500 m, récup 1 min 30', 'Race pace', '{4|6}×400m at 1500m pace, 90 s rest'),
      S('Footing + lignes droites', 'Footing {35|45} min, 6×100 m', 'Run + strides', 'Easy run {35|45} min, 6×100m'),
      S('Lactique', '{3|4}×300 m à allure 800 m, récup 5 min', 'Lactic', '{3|4}×300m at 800m pace, 5 min rest'),
      S('Sortie longue', 'Footing {50|70} min', 'Long run', 'Easy run {50|70} min'),
      COMMON.muscu,
      COMMON.recup,
    ],
    C: [
      S('Rappel d\'allure', '{3|4}×300 m à allure course, récup 3 min', 'Pace reminder', '{3|4}×300m at race pace, 3 min rest'),
      COMMON.preCompet,
      COMMON.compet,
      S('Footing', 'Footing {30|40} min, 4 lignes droites', 'Easy run', 'Easy run {30|40} min, 4 strides'),
      COMMON.recup,
      S('Vitesse', '{4|6}×150 m vite, récup complète', 'Speed', '{4|6}×150m fast, full rest'),
    ],
  },
  long: {
    fr: 'Fond (3 000 m à 10 km)', en: 'Long distance (3000m to 10k)',
    G: [
      S('Endurance fondamentale', 'Footing {40|60} min', 'Easy run', 'Easy run {40|60} min'),
      S('Seuil', '{3|4}×{8|10} min à allure seuil, récup 2 min', 'Threshold', '{3|4}×{8|10} min at threshold, 2 min rest'),
      S('Sortie longue', 'Footing {60|90} min', 'Long run', 'Easy run {60|90} min'),
      COMMON.muscu,
      S('VMA', '{8|12}×400 m à 95 % VMA, récup 1 min', 'Intervals', '{8|12}×400m at 95% vVO2max, 1 min rest'),
      COMMON.recup,
    ],
    S: [
      S('Allure course', '{4|6}×1 000 m à allure 5 km, récup 1 min 30', 'Race pace', '{4|6}×1000m at 5k pace, 90 s rest'),
      S('Endurance', 'Footing {40|60} min', 'Easy run', 'Easy run {40|60} min'),
      S('Sortie longue', 'Footing {70|100} min dont 15 min à allure marathon', 'Long run', 'Easy run {70|100} min incl. 15 min at marathon pace'),
      S('Tempo', '{20|30} min à allure semi-marathon', 'Tempo', '{20|30} min at half-marathon pace'),
      COMMON.muscu,
      COMMON.recup,
    ],
    C: [
      S('Rappel d\'allure', '{3|5}×1 000 m à allure course', 'Pace reminder', '{3|5}×1000m at race pace'),
      COMMON.preCompet,
      COMMON.compet,
      S('Footing', 'Footing {35|45} min', 'Easy run', 'Easy run {35|45} min'),
      COMMON.recup,
      S('Lignes droites', 'Footing 20 min, 8×100 m', 'Strides', 'Easy 20 min, 8×100m'),
    ],
  },
  jumps: {
    fr: 'Sauts (longueur, triple, hauteur)', en: 'Jumps (long, triple, high)',
    G: [
      S('Pliométrie basse', 'Sauts de haies basses {4|6}×6, bonds {4|5}×20 m', 'Low plyometrics', 'Low hurdle hops {4|6}×6, bounds {4|5}×20m'),
      COMMON.muscu,
      S('Vitesse et élan', 'Gammes, {6|8}×40 m progressifs', 'Speed and run-up', 'Drills, {6|8}×40m build-ups'),
      S('Technique courte', '{10|15} sauts à élan réduit (6 foulées)', 'Short approach', '{10|15} jumps from a short (6-stride) approach'),
      COMMON.recup,
      S('Circuit', '{3|4} tours de gainage et proprioception', 'Circuit', '{3|4} rounds of core and balance work'),
    ],
    S: [
      S('Technique élan complet', '{6|10} sauts à élan complet, mesure de l\'élan', 'Full approach', '{6|10} full-approach jumps, check marks'),
      COMMON.muscuMax,
      S('Pliométrie intense', 'Bonds {4|6}×5, sauts en contrebas {3|4}×5', 'Intense plyometrics', 'Bounds {4|6}×5, drop jumps {3|4}×5'),
      S('Vitesse', '{4|6}×30 m lancés', 'Speed', '{4|6}×30m flying'),
      COMMON.recup,
      S('Élan', '{6|8} élans complets sans sauter, régularité des marques', 'Run-up', '{6|8} full run-throughs without jumping, consistent marks'),
    ],
    C: [
      S('Rappel technique', '{4|6} sauts à élan complet à 90 %', 'Technique reminder', '{4|6} full-approach jumps at 90%'),
      COMMON.preCompet,
      COMMON.compet,
      S('Vitesse', '{3|4}×30 m lancés, 2 élans', 'Speed', '{3|4}×30m flying, 2 run-throughs'),
      COMMON.recup,
      COMMON.muscu,
    ],
  },
};

const DAYS = {
  fr: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
  en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
};
// Jours d'entraînement (index 0 = lundi) selon le nombre de séances par semaine.
const DAY_PATTERNS = { 3: [0, 2, 4], 4: [0, 1, 3, 5], 5: [0, 1, 3, 4, 5], 6: [0, 1, 2, 3, 4, 5] };

function fmtVolume(text, level) {
  return text.replace(/\{([^|}]+)\|([^}]+)\}/g, (_, a, b) => (level === 'adv' ? b : a));
}

function phaseSequence(weeks) {
  if (weeks < 4) return [...Array(weeks - 1).fill('C'), 'A'];
  const rest = weeks - 1;
  const g = Math.round(rest * 0.45);
  const s = Math.round(rest * 0.35);
  const c = rest - g - s;
  return [...Array(g).fill('G'), ...Array(s).fill('S'), ...Array(c).fill('C'), 'A'];
}

function weekSessions(group, phase, perWeek, lang, level) {
  const lib = GROUPS[group];
  const days = DAY_PATTERNS[perWeek];
  if (phase === 'A') {
    // Semaine d'affûtage : peu de volume, compétition le dernier jour.
    const base = [lib.C[0], COMMON.recup, lib.C[3], COMMON.recup];
    const picked = base.slice(0, perWeek - 2).concat([COMMON.preCompet, COMMON.compet]);
    return picked.map((s, i) => ({ day: DAYS[lang][days[i]], title: s[lang].t, detail: fmtVolume(s[lang].d, 'beg') }));
  }
  return lib[phase].slice(0, perWeek).map((s, i) => ({ day: DAYS[lang][days[i]], title: s[lang].t, detail: fmtVolume(s[lang].d, level) }));
}

export function buildPlan({ group, weeks, perWeek, level, lang }) {
  const phases = phaseSequence(weeks);
  return phases.map((phase, i) => {
    const deload = (phase === 'G' || phase === 'S') && (i + 1) % 4 === 0;
    const effectiveLevel = deload ? 'beg' : level;
    return {
      week: i + 1,
      phase,
      phaseName: PHASES[phase][lang],
      deload,
      sessions: weekSessions(group, phase, perWeek, lang, effectiveLevel),
    };
  });
}

export const GROUP_NAMES = Object.fromEntries(Object.entries(GROUPS).map(([k, v]) => [k, { fr: v.fr, en: v.en }]));
export { phaseSequence, fmtVolume };
