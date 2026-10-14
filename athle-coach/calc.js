// Calculs de temps : lecture/écriture, temps de passage, prédiction de performance.

export function parseTime(str) {
  const s = String(str).trim().replace(',', '.');
  if (!s) return NaN;
  const parts = s.split(':').map(Number);
  if (parts.some(n => Number.isNaN(n) || n < 0)) return NaN;
  return parts.reduce((acc, n) => acc * 60 + n, 0);
}

export function formatTime(sec, decimals = 2) {
  if (!Number.isFinite(sec)) return '—';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec - h * 3600 - m * 60;
  const ss = s.toFixed(decimals).padStart(decimals ? 3 + decimals : 2, '0');
  if (h) return `${h}:${String(m).padStart(2, '0')}:${ss}`;
  if (m) return `${m}:${ss}`;
  return s.toFixed(decimals);
}

// Temps de passage à allure constante, tous les `step` mètres.
// Le reste tombe au premier passage, comme sur piste (1 500 m : 300, 700, 1 100…).
export function splits(distance, totalSec, step) {
  const out = [];
  for (let d = distance % step || step; d < distance; d += step) out.push({ at: d, time: (totalSec * d) / distance });
  out.push({ at: distance, time: totalSec });
  return out;
}

// Formule de Riegel, fiable de 800 m au marathon.
export function predict(fromDist, fromSec, toDist, exponent = 1.06) {
  return fromSec * Math.pow(toDist / fromDist, exponent);
}

export function pacePerKm(distance, sec) {
  return (sec / distance) * 1000;
}
