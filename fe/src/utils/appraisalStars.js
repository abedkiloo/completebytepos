/** Shared 5-star appraisal colors and display helpers. */

export const APPRAISAL_TONES = {
  rose: {
    bar: 'from-rose-500 to-rose-400',
    text: 'text-rose-700 dark:text-rose-300',
    bg: 'bg-rose-50 dark:bg-rose-950/40',
    border: 'border-rose-200 dark:border-rose-900',
    pill: 'bg-rose-600 text-white',
    emphasisBorder: 'border-rose-400',
    emphasisPanel: 'bg-[#16060c]',
  },
  orange: {
    bar: 'from-orange-500 to-amber-400',
    text: 'text-orange-800 dark:text-orange-300',
    bg: 'bg-orange-50 dark:bg-orange-950/40',
    border: 'border-orange-200 dark:border-orange-900',
    pill: 'bg-orange-500 text-white',
    emphasisBorder: 'border-orange-400',
    emphasisPanel: 'bg-[#1a0c04]',
  },
  amber: {
    bar: 'from-amber-400 to-yellow-300',
    text: 'text-amber-800 dark:text-amber-200',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    border: 'border-amber-200 dark:border-amber-900',
    pill: 'bg-amber-500 text-slate-900',
    emphasisBorder: 'border-amber-400',
    emphasisPanel: 'bg-[#1a1204]',
  },
  emerald: {
    bar: 'from-emerald-500 to-green-400',
    text: 'text-emerald-800 dark:text-emerald-300',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    border: 'border-emerald-200 dark:border-emerald-900',
    pill: 'bg-emerald-600 text-white',
    emphasisBorder: 'border-emerald-400',
    emphasisPanel: 'bg-[#041a12]',
  },
  teal: {
    bar: 'from-teal-500 to-cyan-400',
    text: 'text-teal-800 dark:text-teal-300',
    bg: 'bg-teal-50 dark:bg-teal-950/40',
    border: 'border-teal-200 dark:border-teal-900',
    pill: 'bg-teal-600 text-white',
    emphasisBorder: 'border-teal-400',
    emphasisPanel: 'bg-[#041916]',
  },
  gold: {
    bar: 'from-amber-400 via-yellow-300 to-yellow-100',
    text: 'text-yellow-800 dark:text-yellow-200',
    bg: 'bg-yellow-50 dark:bg-yellow-950/30',
    border: 'border-yellow-300 dark:border-yellow-800',
    pill: 'bg-yellow-400 text-slate-900',
    emphasisBorder: 'border-yellow-400',
    emphasisPanel: 'bg-[#1a1406]',
  },
};

export function appraisalTone(name) {
  return APPRAISAL_TONES[name] || APPRAISAL_TONES.rose;
}

export function starGlyphs(stars, max = 5) {
  const value = Number(stars) || 0;
  const filled = Math.min(max, Math.floor(value));
  const half = value - filled >= 0.5;
  let out = '';
  for (let i = 0; i < max; i += 1) {
    if (i < filled) out += '★';
    else if (i === filled && half) out += '☆';
    else out += '☆';
  }
  return out;
}

export function percentLabel(progress) {
  const value = Math.max(0, Math.min(1, Number(progress) || 0));
  return `${Math.round(value * 100)}%`;
}

export function kes(amount) {
  const n = Number(amount) || 0;
  return `KES ${Math.round(n).toLocaleString('en-KE')}`;
}

export const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];
