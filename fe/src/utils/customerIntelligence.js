/** Labels + help copy for denormalized customer purchase tiers. */

import { LIST_RANK_OPTIONS } from './listOrdering';

export const ENGAGEMENT_TIERS = [
  {
    id: '',
    label: 'All customers',
    tip: 'Show every duka — buyers and registered-only.',
  },
  {
    id: 'buyer',
    label: 'Bought from Omuwenga',
    tip: 'Has completed at least one sale from Omuwenga (not fully refunded).',
  },
  {
    id: 'prospect',
    label: 'Registered only',
    tip: 'In the system but has never completed a purchase from Omuwenga.',
  },
];

/** RFM-lite segments — filter chips when browsing buyers. */
export const BUYER_SEGMENT_FILTERS = [
  {
    id: '',
    label: 'Any segment',
    tip: 'Show all buyers regardless of how recently or often they purchase.',
  },
  {
    id: 'new',
    label: 'New buyer',
    tip: 'First purchase only, and that buy was within the last 30 days.',
  },
  {
    id: 'active',
    label: 'Active',
    tip: 'Bought within the last 30 days (and is not New or Champion).',
  },
  {
    id: 'at_risk',
    label: 'Cooling off',
    tip: 'Last purchase was 31–90 days ago — worth a follow-up before they go quiet.',
  },
  {
    id: 'dormant',
    label: 'Dormant',
    tip: 'No purchase for more than 90 days.',
  },
  {
    id: 'champion',
    label: 'Champion',
    tip: 'At least 5 purchases, lifetime sales of KSh 10,000 or more, and bought within 30 days.',
  },
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

export function engagementTierTooltip(tier) {
  if (tier === 'buyer') {
    return 'Buyer — has completed at least one sale from Omuwenga.';
  }
  if (tier === 'prospect') {
    return 'Registered only — in the system but has never bought from Omuwenga.';
  }
  return '';
}

export function buyerSegmentLabel(segment) {
  switch (segment) {
    case 'new':
      return 'New buyer';
    case 'active':
      return 'Active';
    case 'at_risk':
      return 'Cooling off';
    case 'dormant':
      return 'Dormant';
    case 'champion':
      return 'Champion';
    default:
      return '';
  }
}

export function buyerSegmentTooltip(segment) {
  switch (segment) {
    case 'new':
      return 'New buyer — first purchase only, within the last 30 days.';
    case 'active':
      return 'Active — bought within the last 30 days.';
    case 'at_risk':
      return 'Cooling off — last purchase was 31–90 days ago.';
    case 'dormant':
      return 'Dormant — no purchase for more than 90 days.';
    case 'champion':
      return 'Champion — 5+ purchases, KSh 10,000+ lifetime sales, and bought within 30 days.';
    default:
      return '';
  }
}

export function formatPurchaseCount(count) {
  const n = Number(count) || 0;
  return n === 1 ? '1 purchase' : `${n} purchases`;
}
