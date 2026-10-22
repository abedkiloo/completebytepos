/** Labels for denormalized customer purchase tiers (API engagement_tier / buyer_segment). */

import { LIST_RANK_OPTIONS } from './listOrdering';

export const ENGAGEMENT_TIERS = [
  { id: '', label: 'All customers' },
  { id: 'buyer', label: 'Bought from Omuwenga' },
  { id: 'prospect', label: 'Registered only' },
];

/** RFM-lite segments — filter chips when browsing buyers. */
export const BUYER_SEGMENT_FILTERS = [
  { id: '', label: 'Any segment' },
  { id: 'new', label: 'New buyer' },
  { id: 'active', label: 'Active' },
  { id: 'at_risk', label: 'At risk' },
  { id: 'dormant', label: 'Dormant' },
  { id: 'champion', label: 'Champion' },
];

export const CUSTOMER_RANK_OPTIONS = [
  ...LIST_RANK_OPTIONS,
  { value: '-lifetime_sales_value', label: 'Highest lifetime sales' },
  { value: 'lifetime_sales_value', label: 'Lowest lifetime sales' },
  { value: '-purchase_count', label: 'Most purchases' },
  { value: 'purchase_count', label: 'Fewest purchases' },
  { value: '-last_purchased_at', label: 'Most recent purchase' },
  { value: 'last_purchased_at', label: 'Least recent purchase' },
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

export function formatPurchaseCount(count) {
  const n = Number(count) || 0;
  return n === 1 ? '1 purchase' : `${n} purchases`;
}
