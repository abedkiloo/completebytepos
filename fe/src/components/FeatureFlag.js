import React from 'react';
import { useModuleSettings } from '../hooks/useModuleSettings';
import { isModuleFlagEnabled } from '../utils/moduleSettingsCache';

/**
 * Renders children only when a module setting flag is enabled.
 */
export default function FeatureFlag({
  module,
  flag,
  children,
  fallback = null,
  defaultEnabled = true,
}) {
  const { settings } = useModuleSettings(module);
  if (!isModuleFlagEnabled(settings, flag, defaultEnabled)) {
    return fallback;
  }
  return children;
}
