/** Cached per-module settings (flat key -> value). */

export function flattenModuleSettings(payload) {
  if (!payload?.settings) return {};
  const flat = {};
  Object.entries(payload.settings).forEach(([key, meta]) => {
    flat[key] = meta?.value;
  });
  return flat;
}

export function cacheModuleSettings(module, flatValues) {
  if (!module) return;
  localStorage.setItem(`module_settings_${module}`, JSON.stringify(flatValues || {}));
}

export function readCachedModuleSettings(module) {
  try {
    const raw = localStorage.getItem(`module_settings_${module}`);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function clearModuleSettingsCache(module) {
  if (module) {
    localStorage.removeItem(`module_settings_${module}`);
    return;
  }
  Object.keys(localStorage)
    .filter((k) => k.startsWith('module_settings_'))
    .forEach((k) => localStorage.removeItem(k));
}

export function isModuleFlagEnabled(settings, flag, defaultValue = true) {
  if (!settings || settings[flag] === undefined) return defaultValue;
  return settings[flag] !== false;
}
