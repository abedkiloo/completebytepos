import {
  ENGAGEMENT_TIERS,
  buyerSegmentLabel,
  engagementTierLabel,
} from './customerIntelligence';

describe('customerIntelligence', () => {
  test('tier filters include buyer and prospect', () => {
    expect(ENGAGEMENT_TIERS.map((t) => t.id)).toEqual(['', 'buyer', 'prospect']);
  });

  test('labels', () => {
    expect(engagementTierLabel('buyer')).toBe('Buyer');
    expect(engagementTierLabel('prospect')).toBe('Registered only');
    expect(buyerSegmentLabel('champion')).toBe('Champion');
    expect(buyerSegmentLabel('at_risk')).toBe('At risk');
    expect(buyerSegmentLabel('')).toBe('');
  });
});
