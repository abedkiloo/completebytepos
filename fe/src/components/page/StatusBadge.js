import React from 'react';
import { Badge } from '../ui/badge';

const ACTIVE_VARIANT = { active: 'success', inactive: 'secondary' };

const STATUS_VARIANT = {
  pending: 'warning',
  approved: 'success',
  rejected: 'destructive',
  paid: 'success',
  completed: 'success',
  holding: 'warning',
  cancelled: 'destructive',
};

export function ActiveStatusBadge({ active, labels }) {
  const label = active
    ? labels?.active ?? 'Active'
    : labels?.inactive ?? 'Inactive';
  return (
    <Badge variant={active ? ACTIVE_VARIANT.active : ACTIVE_VARIANT.inactive}>
      {label}
    </Badge>
  );
}

export function StatusBadge({ status, label }) {
  const key = (status || '').toLowerCase();
  const variant = STATUS_VARIANT[key] || 'outline';
  const text =
    label ||
    (key ? key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ') : '—');
  return <Badge variant={variant} className="capitalize">{text}</Badge>;
}
