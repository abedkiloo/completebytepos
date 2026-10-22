import {
  ENGAGEMENT_TIERS,
  buyerSegmentLabel,
  buyerSegmentTooltip,
  engagementTierLabel,
  engagementTierTooltip,
} from './customerIntelligence';

describe('customerIntelligence', () => {
  test('tier filters include buyer and prospect', () => {
    expect(ENGAGEMENT_TIERS.map((t) => t.id)).toEqual(['', 'buyer', 'prospect']);
  });

  test('labels', () => {
    expect(engagementTierLabel('buyer')).toBe('Buyer');
    expect(engagementTierLabel('prospect')).toBe('Registered only');
    expect(buyerSegmentLabel('champion')).toBe('Champion');
    expect(buyerSegmentLabel('at_risk')).toBe('Cooling off');
    expect(buyerSegmentLabel('')).toBe('');
  });

  test('tooltips explain each classification', () => {
    expect(engagementTierTooltip('buyer')).toMatch(/completed at least one sale/i);
    expect(engagementTierTooltip('prospect')).toMatch(/never bought/i);
    expect(buyerSegmentTooltip('new')).toMatch(/30 days/i);
    expect(buyerSegmentTooltip('at_risk')).toMatch(/31–90 days/i);
    expect(buyerSegmentTooltip('champion')).toMatch(/10,000/i);
    expect(buyerSegmentTooltip('dormant')).toMatch(/90 days/i);
  });
});
