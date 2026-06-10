import React from 'react';
import { ShieldAlert } from 'lucide-react';

import { Switch } from '../ui/switch';
import { stripSettingLabelPrefix } from '../../utils/moduleSettingGroups';

/**
 * Single module or store setting row — switch does not auto-commit; parent handles confirm.
 */
export default function SettingToggleRow({
  settingKey,
  item,
  checked,
  disabled,
  onRequestChange,
  requiresApproval,
  testId,
}) {
  const label = stripSettingLabelPrefix(item?.label || settingKey);
  const sensitive = item?.impact === 'high';

  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-border/60 bg-card px-3 py-3">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium leading-snug">{label}</p>
          {sensitive ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
              <ShieldAlert className="h-3 w-3" aria-hidden />
              Sensitive
            </span>
          ) : null}
          {requiresApproval ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              Needs approval
            </span>
          ) : null}
        </div>
        {item?.description ? (
          <p className="text-xs leading-relaxed text-muted-foreground">{item.description}</p>
        ) : null}
      </div>
      <Switch
        id={testId || `setting-${settingKey}`}
        checked={checked}
        disabled={disabled}
        onCheckedChange={(next) => onRequestChange(settingKey, next, item)}
        aria-label={label}
        data-testid={testId}
        className="mt-0.5"
      />
    </div>
  );
}
