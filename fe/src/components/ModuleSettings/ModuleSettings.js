import React, { useState, useEffect, useCallback } from 'react';
import {
  ChevronDown,
  Loader2,
  ShieldCheck,
  Sparkles,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { modulesAPI, moduleFeaturesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { isSuperAdminFromStorage } from '../../utils/navAccess';
import { PageShell, PageHeader, PageLoading } from '../page';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { Separator } from '../ui/separator';
import { cn } from '../../lib/cn';
import { MODULE_ICONS, getFeatureTip } from './moduleSettingsConfig';
import { MODULE_PRESETS } from '../../utils/modulePresets';

function syncModulesCache(data) {
  if (!data) return;
  const copy = { ...data };
  delete copy.catalog;
  localStorage.setItem('enabled_modules', JSON.stringify(copy));
  window.dispatchEvent(new CustomEvent('moduleSettingsUpdated', { detail: copy }));
}

const ModuleSettings = () => {
  const [catalog, setCatalog] = useState([]);
  const [presets, setPresets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [expanded, setExpanded] = useState({});
  const [applyingPreset, setApplyingPreset] = useState(null);

  const isSuperAdmin = isSuperAdminFromStorage();

  const loadModules = useCallback(async () => {
    setLoading(true);
    try {
      const response = await modulesAPI.list();
      const data = response.data || {};
      setCatalog(Array.isArray(data.catalog) ? data.catalog : []);
      setPresets(data._meta?.presets?.length ? data._meta.presets : MODULE_PRESETS);
      const initialExpanded = {};
      (data.catalog || []).forEach((domain) => {
        (domain.modules || []).forEach((mod) => {
          initialExpanded[mod.id] = mod.is_enabled;
        });
      });
      setExpanded(initialExpanded);
      syncModulesCache(data);
    } catch (error) {
      console.error(error);
      toast.error('Failed to load module settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModules();
  }, [loadModules]);

  const handleApplyPreset = async (presetId) => {
    if (!isSuperAdmin) {
      toast.error('Only super admins can apply presets');
      return;
    }
    if (
      !window.confirm(
        'This will enable/disable modules to match the preset. Continue?'
      )
    ) {
      return;
    }
    setApplyingPreset(presetId);
    try {
      const response = await modulesAPI.applyPreset(presetId);
      setCatalog(response.data?.catalog || []);
      syncModulesCache(response.data);
      toast.success('Preset applied — navigation will reflect changes');
      await loadModules();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to apply preset');
    } finally {
      setApplyingPreset(null);
    }
  };

  const handleToggleModule = async (module) => {
    if (!isSuperAdmin) {
      toast.error('Only super admins can change modules');
      return;
    }
    if (module.module_name === 'settings' && module.is_enabled) {
      if (!window.confirm('Disabling Settings locks out configuration. Continue?')) {
        return;
      }
    }

    setSaving((p) => ({ ...p, [module.id]: true }));
    try {
      const next = !module.is_enabled;
      await modulesAPI.update(module.id, { ...module, is_enabled: next });

      if (!next) {
        const features = Object.values(module.features || {});
        await Promise.all(
          features.filter((f) => f?.id).map((f) => moduleFeaturesAPI.patch(f.id, { is_enabled: false }))
        );
      } else {
        setExpanded((p) => ({ ...p, [module.id]: true }));
      }

      const refreshed = await modulesAPI.list();
      setCatalog(refreshed.data?.catalog || []);
      syncModulesCache(refreshed.data);
      toast.success(`${module.module_name_display} ${next ? 'enabled' : 'disabled'}`);
    } catch (error) {
      toast.error(error.response?.data?.error || 'Update failed');
    } finally {
      setSaving((p) => ({ ...p, [module.id]: false }));
    }
  };

  const handleToggleFeature = async (module, featureKey) => {
    if (!isSuperAdmin) {
      toast.error('Only super admins can change features');
      return;
    }
    if (!module.is_enabled) {
      toast.warning('Enable the module first');
      return;
    }
    const feature = module.features?.[featureKey];
    if (!feature?.id) {
      await loadModules();
      return;
    }

    setSaving((p) => ({ ...p, [`f-${feature.id}`]: true }));
    try {
      const next = !feature.is_enabled;
      await moduleFeaturesAPI.patch(feature.id, { is_enabled: next });
      const refreshed = await modulesAPI.list();
      setCatalog(refreshed.data?.catalog || []);
      syncModulesCache(refreshed.data);
      toast.success(`${feature.feature_name} ${next ? 'on' : 'off'}`);
    } catch (error) {
      toast.error(error.response?.data?.error || 'Update failed');
    } finally {
      setSaving((p) => ({ ...p, [`f-${feature.id}`]: false }));
    }
  };

  const renderModuleCard = (module, { nested = false } = {}) => {
    const Icon = MODULE_ICONS[module.module_name] || Layers;
    const features = Object.entries(module.features || {}).sort(
      ([, a], [, b]) => (a.display_order || 0) - (b.display_order || 0)
    );
    const isOpen = expanded[module.id];
    const enabledFeatures = features.filter(([, f]) => f.is_enabled).length;
    const critical = module.module_name === 'settings';

    return (
      <Card
        key={module.id}
        className={cn(
          'overflow-hidden',
          nested && 'border-dashed bg-muted/10',
          module.is_enabled ? 'border-primary/20 shadow-sm' : 'opacity-90'
        )}
      >
        <CardHeader className="flex flex-row items-start gap-3 space-y-0 pb-3">
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
              module.is_enabled ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
            )}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="text-base">{module.module_name_display}</CardTitle>
              {critical && <Badge variant="warning">Critical</Badge>}
              {module.rollup_under && <Badge variant="outline">Legacy</Badge>}
              {!module.is_enabled && <Badge variant="secondary">Off</Badge>}
            </div>
            <CardDescription className="mt-1 line-clamp-2">
              {module.description}
            </CardDescription>
            {features.length > 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                {enabledFeatures}/{features.length} features on
              </p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {saving[module.id] ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            ) : (
              <Switch
                checked={module.is_enabled}
                disabled={!isSuperAdmin}
                onCheckedChange={() => handleToggleModule(module)}
              />
            )}
            {features.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() =>
                  setExpanded((p) => ({ ...p, [module.id]: !p[module.id] }))
                }
              >
                <ChevronDown
                  className={cn('h-4 w-4 transition-transform', isOpen && 'rotate-180')}
                />
              </Button>
            )}
          </div>
        </CardHeader>

        {isOpen && features.length > 0 && (
          <>
            <Separator />
            <CardContent className="space-y-3 pt-4">
              {!module.is_enabled && (
                <p className="text-xs text-amber-700 dark:text-amber-200">
                  Enable this module to configure features.
                </p>
              )}
              {features.map(([featureKey, feature]) => (
                <div
                  key={feature.id || featureKey}
                  className="flex items-start justify-between gap-3 rounded-md border bg-muted/20 px-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{feature.feature_name}</p>
                    {feature.description && (
                      <p className="text-xs text-muted-foreground">{feature.description}</p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground/80">
                      {getFeatureTip(module.module_name, featureKey)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={feature.is_enabled ? 'success' : 'outline'} className="text-xs">
                      {feature.is_enabled ? 'On' : 'Off'}
                    </Badge>
                    {saving[`f-${feature.id}`] ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Switch
                        checked={feature.is_enabled}
                        disabled={!isSuperAdmin || !module.is_enabled}
                        onCheckedChange={() => handleToggleFeature(module, featureKey)}
                      />
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </>
        )}

        {module.rollup_children?.length > 0 && module.is_enabled && (
          <CardContent className="space-y-2 border-t bg-muted/5 pt-4">
            <p className="text-xs font-medium text-muted-foreground">
              Legacy module rows (prefer features above)
            </p>
            {module.rollup_children.map((child) => renderModuleCard(child, { nested: true }))}
          </CardContent>
        )}
      </Card>
    );
  };

  if (loading) {
    return (
      <PageLoading rows={10} />
    );
  }

  return (
    <PageShell>
        <PageHeader
          title="App modules"
          description="Organize capabilities by business area. Toggles update the menu, APIs, and roles together."
        >
          {isSuperAdmin && (
            <Badge variant="success" className="gap-1">
              <ShieldCheck className="h-3.5 w-3.5" />
              Super admin
            </Badge>
          )}
        </PageHeader>

        {!isSuperAdmin && (
          <Card className="border-warning/40 bg-warning/10">
            <CardContent className="flex gap-3 p-4 text-sm">
              <AlertTriangle className="h-5 w-5 shrink-0 text-warning" />
              <p>View-only. Ask a super admin to change modules or apply a preset.</p>
            </CardContent>
          </Card>
        )}

        {isSuperAdmin && presets.length > 0 && (
          <Card className="border-primary/25">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-5 w-5 text-primary" />
                Quick setup presets
              </CardTitle>
              <CardDescription>
                Same presets used during installation — one click to match your store type.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  disabled={!!applyingPreset}
                  onClick={() => handleApplyPreset(preset.id)}
                  className={cn(
                    'rounded-lg border bg-card p-4 text-left transition hover:border-primary/40 hover:bg-primary/5',
                    applyingPreset === preset.id && 'ring-2 ring-primary'
                  )}
                >
                  <p className="font-semibold">{preset.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{preset.description}</p>
                  {applyingPreset === preset.id && (
                    <Loader2 className="mt-2 h-4 w-4 animate-spin text-primary" />
                  )}
                </button>
              ))}
            </CardContent>
          </Card>
        )}

        <div className="space-y-10">
          {catalog.map((domain) => (
            <section key={domain.id} className="space-y-3">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{domain.label}</h2>
                <p className="text-sm text-muted-foreground">{domain.description}</p>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {(domain.modules || []).map((mod) => renderModuleCard(mod))}
              </div>
            </section>
          ))}
        </div>
      </PageShell>
  );
};

export default ModuleSettings;
