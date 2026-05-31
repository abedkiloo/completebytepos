import React from 'react';
import { AlertTriangle } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { toast } from '../../utils/toast';

const HIGH_IMPACT_CONFIRM =
  'This setting affects checkout, permissions, stock rules, or data access. Continue?';

/**
 * Shared System Settings card for one module's ModuleSetting toggles.
 */
export default function ModuleSettingsCard({ module, title, description, icon: Icon, toastLabel }) {
  const { settings, meta, loading, patch } = useModuleSettings(module);

  const entries = meta?.settings
    ? Object.entries(meta.settings).sort(
        ([, a], [, b]) => (a.display_order ?? 0) - (b.display_order ?? 0)
      )
    : [];

  const onToggle = async (key, checked, item) => {
    if (item.impact === 'high' && !window.confirm(HIGH_IMPACT_CONFIRM)) {
      return;
    }
    try {
      await patch({ [key]: checked });
      toast.success(`${toastLabel} settings updated`);
    } catch (err) {
      toast.error(err.response?.data?.detail || `Could not update ${toastLabel.toLowerCase()} settings`);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          {Icon ? <Icon className="h-4 w-4 text-primary" /> : null}
          {title}
        </CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {entries.length === 0 && !loading && (
          <p className="text-muted-foreground">No settings loaded.</p>
        )}
        {entries.map(([key, item]) => (
          <label key={key} className="flex items-start gap-2">
            <input
              type="checkbox"
              disabled={loading}
              checked={settings[key] !== false}
              onChange={(e) => onToggle(key, e.target.checked, item)}
              className="mt-0.5"
              data-testid={`setting-${module}-${key}`}
            />
            <span>
              <span className="inline-flex flex-wrap items-center gap-1.5">
                <span className="font-medium">{item.label || key}</span>
                {item.impact === 'high' ? (
                  <span className="inline-flex items-center gap-0.5 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400">
                    <AlertTriangle className="h-3 w-3" aria-hidden />
                    High impact
                  </span>
                ) : null}
              </span>
              {item.description ? (
                <span className="mt-0.5 block text-muted-foreground">{item.description}</span>
              ) : null}
            </span>
          </label>
        ))}
      </CardContent>
    </Card>
  );
}
