import { kes, percentLabel, starGlyphs } from './appraisalStars';

describe('appraisalStars helpers', () => {
  test('star glyphs fill from the rating', () => {
    expect(starGlyphs(1)).toBe('★☆☆☆☆');
    expect(starGlyphs(4)).toBe('★★★★☆');
    expect(starGlyphs(5)).toBe('★★★★★');
    expect(starGlyphs(4.5)).toBe('★★★★☆');
  });

  test('percent and KES labels', () => {
    expect(percentLabel(0.625)).toBe('63%');
    expect(percentLabel(1.4)).toBe('100%');
    expect(kes(1500)).toBe('KES 1,500');
    expect(kes(18000)).toBe('KES 18,000');
  });
});
