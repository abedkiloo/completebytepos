import React from 'react';
import { Badge } from '../ui/badge';
import { formatPendingApprovalHint, pendingApprovalLabels } from '../../utils/makerChecker';

export default function PendingApprovalBadges({ pendingApproval, className = '' }) {
  const labels = pendingApprovalLabels(pendingApproval);
  if (!labels.length) return null;
  return (
    <span className={`inline-flex flex-wrap gap-1 ${className}`}>
      {labels.map((label) => (
        <Badge key={label} variant="warning" className="px-1.5 py-0 text-[10px]">
          Pending {label}
        </Badge>
      ))}
    </span>
  );
}
