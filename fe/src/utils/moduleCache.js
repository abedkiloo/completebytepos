/**
 * Normalize enabled_modules from API, login, or legacy boolean maps.
 */

export function normalizeModuleEntry(entry) {
  if (entry == null) return null;
  if (typeof entry === 'boolean') {
    return { is_enabled: entry, features: {} };
  }
  if (typeof entry === 'object') {
    return {
      ...entry,
      is_enabled: Boolean(entry.is_enabled),
      features: entry.features && typeof entry.features === 'object' ? entry.features : {},
    };
  }
  return null;
}

/** Strip catalog/_meta and coerce legacy boolean values. */
export function normalizeModuleSettings(raw) {
  if (!raw || typeof raw !== 'object') return {};
  const out = {};
  if (raw.registry && typeof raw.registry === 'object') {
    out.registry = raw.registry;
  }
  Object.entries(raw).forEach(([key, value]) => {
    if (key === 'catalog' || key === 'registry' || key.startsWith('_')) return;
    const normalized = normalizeModuleEntry(value);
    if (normalized) out[key] = normalized;
  });
  return out;
}

/** Registry default for a feature when the row is missing from cache (mirrors backend). */
export function registryFeatureDefault(moduleSettings, moduleName, featureKey) {
  const fromApi =
    moduleSettings?.registry?.feature_defaults?.[moduleName]?.[featureKey];
  if (fromApi !== undefined) return Boolean(fromApi);
  return true;
}

export function isRichModulePayload(modules) {
  if (!modules || typeof modules !== 'object') return false;
  const keys = Object.keys(modules).filter((k) => k !== 'catalog' && !k.startsWith('_'));
  if (!keys.length) return false;
  const sample = modules[keys[0]];
  return sample != null && typeof sample === 'object' && 'is_enabled' in sample;
}

export function readCachedModules() {
  try {
    return normalizeModuleSettings(JSON.parse(localStorage.getItem('enabled_modules') || '{}'));
  } catch {
    return {};
  }
}

export function isModuleEnabledInSettings(moduleSettings, moduleName, { loading = false } = {}) {
  if (!moduleName) return true;
  let settings = moduleSettings;
  if (loading && (!settings || Object.keys(settings).length === 0)) {
    settings = readCachedModules();
    if (Object.keys(settings).length === 0) return true;
  } else if (loading) {
    // Refresh in background — keep using current settings, do not show everything.
    settings = moduleSettings;
  }
  if (!settings || Object.keys(settings).length === 0) return true;
  const mod = settings[moduleName];
  if (mod == null) return true;
  return Boolean(mod.is_enabled);
}

export function isFeatureEnabledInSettings(
  moduleSettings,
  moduleName,
  featureKey,
  { loading = false, defaultWhenMissing = false } = {}
) {
  let settings = moduleSettings;
  if (loading && (!settings || Object.keys(settings).length === 0)) {
    settings = readCachedModules();
    if (Object.keys(settings).length === 0) return true;
  }
  const mod = settings[moduleName];
  if (!mod || !mod.is_enabled) return false;
  const feature = (mod.features || {})[featureKey];
  if (feature == null) return defaultWhenMissing;
  return Boolean(feature.is_enabled);
}
