import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { toast } from '../../utils/toast';
import {
  extractApiReasonError,
  isMakerCheckerEnabled,
  pendingApprovalToastMessage,
  userMayReviewPendingApprovals,
} from '../../utils/makerChecker';
import { groupModuleSettings } from '../../utils/moduleSettingGroups';
import { cn } from '../../lib/cn';
import SettingToggleRow from './SettingToggleRow';
import ModuleSettingChangeDialog from './ModuleSettingChangeDialog';

/**
 * Collapsible module settings — in-app confirm dialog instead of browser alert/prompt.
 */
export default function ModuleSettingsCard({
  module,
  title,
  description,
  icon: Icon,
  toastLabel,
  expanded = false,
  onToggleExpand,
}) {
  const { settings, meta, loading, patch } = useModuleSettings(module);
  const { settings: storeSettings } = useStoreSettings();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const userMayApprove = userMayReviewPendingApprovals();

  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);

  const entries = meta?.settings
    ? Object.entries(meta.settings).sort(
        ([, a], [, b]) => (a.display_order ?? 0) - (b.display_order ?? 0)
      )
    : [];

  const groups = useMemo(() => groupModuleSettings(entries), [entries]);
  const enabledCount = entries.filter(([key]) => settings[key] !== false).length;

  const needsDialog = (item) => item?.impact === 'high' || makerCheckerOn;

  const applyChange = async (key, checked, item, reason) => {
    setBusy(true);
    try {
      const result = await patch(
        { [key]: checked },
        { reason: reason?.trim() || undefined }
      );
      if (result?.pending) {
        toast.warning(pendingApprovalToastMessage());
      } else {
        toast.success(`${toastLabel} settings updated`);
      }
      setPending(null);
    } catch (err) {
      const detail = err.response?.data;
      toast.error(
        extractApiReasonError(detail) ||
          detail?.detail ||
          `Could not update ${toastLabel.toLowerCase()} settings`
      );
    } finally {
      setBusy(false);
    }
  };

  const handleRequestChange = (key, checked, item) => {
    if (needsDialog(item)) {
      setPending({ key, checked, item });
      return;
    }
    applyChange(key, checked, item);
  };

  const handleConfirm = (reason) => {
    if (!pending) return;
    applyChange(pending.key, pending.checked, pending.item, reason);
  };

  return (
    <>
      <Card className={cn('overflow-hidden', expanded && 'ring-1 ring-primary/20')}>
        <button
          type="button"
          className="flex w-full items-start gap-3 px-6 py-4 text-left transition-colors hover:bg-muted/30"
          onClick={onToggleExpand}
          aria-expanded={expanded}
          data-testid={`module-settings-card-${module}`}
        >
          <div className="rounded-md bg-primary/10 p-2 text-primary">
            {Icon ? <Icon className="h-4 w-4" /> : null}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">{title}</CardTitle>
              <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                {enabledCount}/{entries.length || '—'} on
              </span>
            </div>
            {description ? (
              <CardDescription className="mt-1 text-left">{description}</CardDescription>
            ) : null}
          </div>
          <ChevronDown
            className={cn(
              'mt-1 h-5 w-5 shrink-0 text-muted-foreground transition-transform',
              expanded && 'rotate-180'
            )}
            aria-hidden
          />
        </button>

        {expanded ? (
          <CardContent className="space-y-4 border-t pt-4">
            {entries.length === 0 && !loading ? (
              <p className="text-sm text-muted-foreground">No settings loaded.</p>
            ) : null}
            {loading && entries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : null}

            {groups.map((group) => (
              <div key={group.id} className="space-y-2">
                {groups.length > 1 ? (
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {group.label}
                  </p>
                ) : null}
                <div className="space-y-2">
                  {group.items.map(([key, item]) => (
                    <SettingToggleRow
                      key={key}
                      settingKey={key}
                      item={item}
                      checked={settings[key] !== false}
                      disabled={loading || busy}
                      requiresApproval={makerCheckerOn && item.impact === 'high'}
                      onRequestChange={handleRequestChange}
                      testId={`setting-${module}-${key}`}
                    />
                  ))}
                </div>
              </div>
            ))}

            {makerCheckerOn ? (
              <p className="text-xs text-muted-foreground">
                Changes here may require manager approval before they affect POS and permissions.
              </p>
            ) : null}
          </CardContent>
        ) : null}
      </Card>

      <ModuleSettingChangeDialog
        open={Boolean(pending)}
        onOpenChange={(open) => {
          if (!open && !busy) setPending(null);
        }}
        setting={pending?.item}
        enabling={pending?.checked}
        makerCheckerOn={makerCheckerOn}
        userMayApprove={userMayApprove}
        onConfirm={handleConfirm}
        busy={busy}
      />
    </>
  );
}
