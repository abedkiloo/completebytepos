import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardCheck } from 'lucide-react';

import { inventoryAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { getStoredAuth, hasPermission, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { Badge } from '../ui/badge';

/**
 * Admin-visible closed stock checkpoints (reporting baselines).
 * Non-admins who can view inventory.manage still see markers when granted.
 */
export default function CheckpointMarkersStrip({ className = '' }) {
  const { permissions } = getStoredAuth();
  const canSee =
    isManagerOrAdminFromStorage() ||
    hasPermission(permissions, 'inventory', 'manage') ||
    hasPermission(permissions, 'reports', 'view');

  const [baselines, setBaselines] = useState([]);
  const [latestAt, setLatestAt] = useState(null);

  useEffect(() => {
    if (!canSee) return undefined;
    let active = true;
    inventoryAPI
      .checkpointBaselines()
      .then((res) => {
        if (!active) return;
        setBaselines(res.data?.results || []);
        setLatestAt(res.data?.latest_closed_at || null);
      })
      .catch(() => {
        if (!active) return;
        setBaselines([]);
        setLatestAt(null);
      });
    return () => {
      active = false;
    };
  }, [canSee]);

  if (!canSee || baselines.length === 0) return null;

  return (
    <div
      className={`rounded-lg border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm text-sky-950 ${className}`}
      data-testid="checkpoint-markers"
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2 font-semibold">
        <ClipboardCheck className="h-4 w-4" />
        Stock checkpoints (report baselines)
        {latestAt ? (
          <span className="font-normal text-sky-900">
            · Journey from {formatDateTime(latestAt)}
          </span>
        ) : null}
        {hasPermission(permissions, 'inventory', 'manage') ? (
          <Link to="/inventory/checkpoints" className="ml-auto text-xs font-medium underline">
            Manage
          </Link>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {baselines.slice(0, 8).map((cp) => (
          <Badge key={cp.id} variant="outline" className="bg-white text-xs font-normal">
            {cp.title}
            {cp.closed_at ? ` · ${formatDateTime(cp.closed_at)}` : ''}
            {cp.inventory_value_after != null
              ? ` · ${formatCurrency(cp.inventory_value_after)}`
              : ''}
          </Badge>
        ))}
      </div>
    </div>
  );
}
