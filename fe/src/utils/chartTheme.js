/**
 * Chart colours stay inside the Omuwenga navy/steel theme.
 *
 * Series differentiation uses only primary/accent blues — not rainbow
 * accents. Status outliers (success / warning / destructive) are reserved
 * for buttons, badges, and severity (profit, aging, low-stock).
 */

/** HSL triplets matching ``--chart-*`` in index.css (no hsl() wrapper). */
export const CHART_SERIES_HSL = [
  '214 73% 19%', // primary navy
  '209 29% 55%', // steel accent
  '214 40% 38%', // mid navy
  '210 25% 68%', // light steel
  '214 33% 48%', // blue-gray
  '210 18% 42%', // muted ink
];

/** Ready-to-paint fills/strokes for Recharts (and similar). */
export const CHART_SERIES = CHART_SERIES_HSL.map((triplet) => `hsl(${triplet})`);

/** Semantic outliers — use sparingly for status / severity only. */
export const CHART_STATUS = {
  success: 'hsl(142 68% 37%)',
  warning: 'hsl(32 95% 44%)',
  destructive: 'hsl(0 72% 51%)',
};

/**
 * Pick a series colour by index (wraps).
 *
 * @param {number} index Zero-based series index.
 * @returns {string} ``hsl(...)`` colour string.
 */
export function chartSeriesColor(index) {
  const i = Math.abs(Number(index) || 0) % CHART_SERIES.length;
  return CHART_SERIES[i];
}

/**
 * Aging / risk ramp: theme blues, then warning, then destructive.
 *
 * @param {number} index Bucket index, oldest usually last.
 * @param {number} [bucketCount=4] Total buckets (2–8).
 * @returns {string} Paint colour.
 */
export function chartAgingColor(index, bucketCount = 4) {
  const count = Math.max(2, Math.min(8, Number(bucketCount) || 4));
  const i = Math.max(0, Math.min(count - 1, Number(index) || 0));
  if (i >= count - 1) return CHART_STATUS.destructive;
  if (i >= count - 2) return CHART_STATUS.warning;
  return chartSeriesColor(i);
}
