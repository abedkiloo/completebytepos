import {
  CHART_SERIES,
  CHART_STATUS,
  chartAgingColor,
  chartSeriesColor,
} from './chartTheme';

describe('chartTheme', () => {
  test('series stays in navy/steel hsl family', () => {
    expect(CHART_SERIES.length).toBeGreaterThanOrEqual(4);
    CHART_SERIES.forEach((color) => {
      expect(color).toMatch(/^hsl\((209|210|214) /);
    });
  });

  test('chartSeriesColor wraps', () => {
    expect(chartSeriesColor(0)).toBe(CHART_SERIES[0]);
    expect(chartSeriesColor(CHART_SERIES.length)).toBe(CHART_SERIES[0]);
  });

  test('aging uses theme then status outliers', () => {
    expect(chartAgingColor(0, 4)).toBe(CHART_SERIES[0]);
    expect(chartAgingColor(1, 4)).toBe(CHART_SERIES[1]);
    expect(chartAgingColor(2, 4)).toBe(CHART_STATUS.warning);
    expect(chartAgingColor(3, 4)).toBe(CHART_STATUS.destructive);
  });

  test('status outliers stay semantic only', () => {
    expect(CHART_STATUS.success).toContain('142');
    expect(CHART_STATUS.warning).toContain('32');
    expect(CHART_STATUS.destructive).toContain('0 ');
  });
});
