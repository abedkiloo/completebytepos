/**
 * Utility functions to check module and feature settings
 * These functions read from localStorage cache or can be used with module settings object
 */

/**
 * Get module settings from localStorage cache
 * @returns {Object} Module settings object
 */
export const getModuleSettings = () => {
  try {
    const cached = localStorage.getItem('enabled_modules');
    return cached ? JSON.parse(cached) : {};
  } catch (error) {
    console.error('Error reading module settings from cache:', error);
    return {};
  }
};

/**
 * Check if a module is enabled
 * @param {string} moduleName - Name of the module (e.g., 'stock', 'sales')
 * @param {Object} moduleSettings - Optional module settings object (if not provided, reads from cache)
 * @returns {boolean} True if module is enabled
 */
export const isModuleEnabled = (moduleName, moduleSettings = null) => {
  const settings = moduleSettings || getModuleSettings();
  if (!settings || Object.keys(settings).length === 0) {
    return true; // Default to enabled if not configured
  }
  const module = settings[moduleName];
  return module ? module.is_enabled : true; // Default to enabled if not configured
};

/**
 * Check if a feature within a module is enabled
 * @param {string} moduleName - Name of the module (e.g., 'stock', 'sales', 'inventory')
 * @param {string} featureKey - Key of the feature (e.g., 'stock_adjustments', 'pos')
 * @param {Object} moduleSettings - Optional module settings object (if not provided, reads from cache)
 * @returns {boolean} True if feature is enabled
 */
export const isFeatureEnabled = (moduleName, featureKey, moduleSettings = null) => {
  const settings = moduleSettings || getModuleSettings();
  if (!settings || Object.keys(settings).length === 0) {
    return true; // Default to enabled if not configured
  }
  const module = settings[moduleName];
  if (!module || !module.is_enabled) {
    return false; // Module must be enabled first
  }
  const features = module.features || {};
  const feature = features[featureKey];
  // If feature doesn't exist, default to enabled (for backward compatibility)
  // If feature exists, check its is_enabled status
  return feature ? feature.is_enabled : true;
};

/**
 * Check if a feature is enabled in any of the provided modules
 * Useful when a feature exists in multiple modules (e.g., stock_adjustments in both 'inventory' and 'stock')
 * @param {string[]} moduleNames - Array of module names to check
 * @param {string} featureKey - Key of the feature
 * @param {Object} moduleSettings - Optional module settings object
 * @returns {boolean} True if feature is enabled in any of the modules
 */
export const isFeatureEnabledInAny = (moduleNames, featureKey, moduleSettings = null) => {
  return moduleNames.some(moduleName => isFeatureEnabled(moduleName, featureKey, moduleSettings));
};
