/** Labels for denormalized customer purchase tiers (API engagement_tier / buyer_segment). */

export const ENGAGEMENT_TIERS = [
  { id: '', label: 'All customers' },
  { id: 'buyer', label: 'Bought from Omuwenga' },
  { id: 'prospect', label: 'Registered only' },
];

export function engagementTierLabel(tier) {
  if (tier === 'buyer') return 'Buyer';
  if (tier === 'prospect') return 'Registered only';
  return '';
}

export function buyerSegmentLabel(segment) {
  switch (segment) {
    case 'new':
      return 'New buyer';
    case 'active':
      return 'Active';
    case 'at_risk':
      return 'At risk';
    case 'dormant':
      return 'Dormant';
    case 'champion':
      return 'Champion';
    default:
      return '';
  }
}
