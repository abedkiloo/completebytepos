import React, { useState, useEffect } from 'react';
import { modulesAPI, moduleFeaturesAPI } from '../../services/api';
import Layout from '../Layout/Layout';
import { toast } from '../../utils/toast';
import './ModuleSettings.css';

const ModuleSettings = () => {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [expandedModules, setExpandedModules] = useState({});
  
  // Check if user is super admin
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userProfile = user.profile || {};
  const isSuperAdmin = userProfile.role === 'super_admin' || user.is_superuser || userProfile.is_super_admin;

  useEffect(() => {
    loadModules();
  }, []);

  const loadModules = async () => {
    setLoading(true);
    try {
      const response = await modulesAPI.list();
      const modulesData = response.data || {};
      
      // Convert object to array for easier rendering
      const modulesArray = Object.keys(modulesData).map(key => ({
        id: modulesData[key].id,
        module_name: key,
        module_name_display: modulesData[key].module_name_display || key,
        is_enabled: modulesData[key].is_enabled,
        description: modulesData[key].description || '',
        features: modulesData[key].features || {},
      }));
      
      // Sort by module name
      modulesArray.sort((a, b) => a.module_name_display.localeCompare(b.module_name_display));
      
      // Initialize expanded state - expand enabled modules by default
      const initialExpanded = {};
      modulesArray.forEach(module => {
        initialExpanded[module.id] = module.is_enabled;
      });
      setExpandedModules(initialExpanded);
      
      setModules(modulesArray);
    } catch (error) {
      console.error('Error loading modules:', error);
      toast.error('Failed to load module settings');
    } finally {
      setLoading(false);
    }
  };

  const toggleModuleExpansion = (moduleId) => {
    setExpandedModules(prev => ({
      ...prev,
      [moduleId]: !prev[moduleId]
    }));
  };

  const handleToggleModule = async (module) => {
    // Check if user is super admin
    if (!isSuperAdmin) {
      toast.error('Only super admins can modify module settings');
      return;
    }
    
    // Prevent disabling the settings module itself (would lock out super admins)
    if (module.module_name === 'settings' && module.is_enabled) {
      const confirmed = window.confirm(
        'Warning: Disabling the Settings module will prevent access to module settings. Are you sure you want to continue?'
      );
      if (!confirmed) {
        return;
      }
    }
    
    setSaving(prev => ({ ...prev, [module.id]: true }));
    try {
      const newEnabledState = !module.is_enabled;
      const updatedModule = {
        ...module,
        is_enabled: newEnabledState,
      };
      
      await modulesAPI.update(module.id, updatedModule);
      
      // If disabling module, disable all features
      if (!newEnabledState) {
        const features = Object.values(module.features || {});
        const featureUpdates = features.map(feature => ({
          ...feature,
          is_enabled: false,
        }));
        
        // Update all features in parallel
        await Promise.all(
          featureUpdates.map(feature => 
            moduleFeaturesAPI.update(feature.id, feature)
          )
        );
        
        // Update local state for all features
        setModules(prevModules =>
          prevModules.map(m => {
            if (m.id === module.id) {
              const updatedFeatures = {};
              Object.keys(m.features).forEach(key => {
                updatedFeatures[key] = { ...m.features[key], is_enabled: false };
              });
              return {
                ...m,
                is_enabled: newEnabledState,
                features: updatedFeatures,
              };
            }
            return m;
          })
        );
      } else {
        // If enabling module, expand it
        setExpandedModules(prev => ({ ...prev, [module.id]: true }));
      }
      
      setModules(prevModules =>
        prevModules.map(m =>
          m.id === module.id ? { ...m, is_enabled: newEnabledState } : m
        )
      );
      
      toast.success(`${module.module_name_display} ${newEnabledState ? 'enabled' : 'disabled'} successfully`);
      
      // Refresh module settings cache in localStorage
      const updatedResponse = await modulesAPI.list();
      if (updatedResponse.data) {
        localStorage.setItem('enabled_modules', JSON.stringify(updatedResponse.data));
        // Trigger a custom event to notify other components
        window.dispatchEvent(new CustomEvent('moduleSettingsUpdated', { detail: updatedResponse.data }));
      }
    } catch (error) {
      console.error('Error updating module:', error);
      toast.error(`Failed to update ${module.module_name_display}: ${error.response?.data?.error || error.message}`);
    } finally {
      setSaving(prev => ({ ...prev, [module.id]: false }));
    }
  };

  const handleToggleFeature = async (module, featureKey) => {
    // Check if user is super admin
    if (!isSuperAdmin) {
      toast.error('Only super admins can modify module features');
      return;
    }
    
    const feature = module.features[featureKey];
    if (!feature) return;
    
    // Don't allow toggling features if module is disabled
    if (!module.is_enabled) {
      toast.warning('Please enable the module first to manage its features');
      return;
    }
    
    setSaving(prev => ({ ...prev, [`feature-${feature.id}`]: true }));
    try {
      // Only send fields that can be updated (exclude read-only fields)
      // The serializer requires 'module' and 'feature_key' but they should already be set
      const updatedFeature = {
        is_enabled: !feature.is_enabled,
      };
      
      // Use PATCH instead of PUT to only update the is_enabled field
      await moduleFeaturesAPI.patch(feature.id, updatedFeature);
      
      setModules(prevModules =>
        prevModules.map(m => {
          if (m.id === module.id) {
            return {
              ...m,
              features: {
                ...m.features,
                [featureKey]: updatedFeature,
              },
            };
          }
          return m;
        })
      );
      
      toast.success(`${feature.feature_name} ${updatedFeature.is_enabled ? 'enabled' : 'disabled'} successfully`);
      
      // Refresh module settings cache in localStorage
      const updatedResponse = await modulesAPI.list();
      if (updatedResponse.data) {
        localStorage.setItem('enabled_modules', JSON.stringify(updatedResponse.data));
        // Trigger a custom event to notify other components
        window.dispatchEvent(new CustomEvent('moduleSettingsUpdated', { detail: updatedResponse.data }));
      }
    } catch (error) {
      console.error('Error updating feature:', error);
      toast.error(`Failed to update feature: ${error.response?.data?.error || error.message}`);
    } finally {
      setSaving(prev => ({ ...prev, [`feature-${feature.id}`]: false }));
    }
  };

  const getModuleIcon = (moduleName) => {
    const icons = {
      'products': '📦',
      'sales': '🛒',
      'customers': '👥',
      'invoicing': '📄',
      'inventory': '📦',
      'stock': '📊',
      'expenses': '💸',
      'income': '💰',
      'bank_accounts': '🏦',
      'money_transfer': '🔄',
      'accounting': '📊',
      'balance_sheet': '📋',
      'trial_balance': '⚖️',
      'cash_flow': '💵',
      'account_statement': '📄',
      'suppliers': '🏭',
      'barcodes': '🏷️',
      'reports': '📈',
      'settings': '⚙️',
    };
    return icons[moduleName] || '⚙️';
  };

  const getModuleTips = (moduleName) => {
    const tips = {
      'products': 'Manage product catalog with categories, variants, pricing, and inventory. Essential for sales.',
      'sales': 'Process sales via POS (quick) or Normal Sales (with invoicing). Track all transactions.',
      'customers': 'Maintain customer database with contact info, purchase history, and wallet balances.',
      'invoicing': 'Create invoices, track payments (full/partial), and manage payment plans.',
      'inventory': 'Track stock levels, movements, low stock alerts, and adjustments.',
      'stock': 'Advanced stock management with transfers, adjustments, and reorder points.',
      'expenses': 'Record and categorize business expenses for financial tracking.',
      'income': 'Track non-sales income sources and revenue streams.',
      'bank_accounts': 'Manage multiple bank accounts and track balances.',
      'money_transfer': 'Transfer funds between accounts and track movements.',
      'accounting': 'Full accounting with chart of accounts, journal entries, and double-entry bookkeeping.',
      'balance_sheet': 'Generate balance sheets showing assets, liabilities, and equity.',
      'trial_balance': 'Verify accounting records are balanced (debits = credits).',
      'cash_flow': 'Track money flow in and out of your business.',
      'account_statement': 'View detailed bank statements with transactions and balances.',
      'barcodes': 'Generate barcodes/QR codes and print labels for products.',
      'reports': 'Access sales, product, inventory, and financial reports.',
      'settings': 'Configure system settings, users, roles, and permissions.',
    };
    return tips[moduleName] || 'Module configuration and settings';
  };

  const getFeatureTips = (moduleName, featureKey) => {
    const featureTips = {
      'products': {
        'qr_printing': 'Generate QR codes for mobile scanning and quick product lookup.',
        'barcode_printing': 'Create barcodes (EAN, UPC) for checkout scanning.',
        'product_variants': 'Enable products with sizes/colors variants for flexible inventory.',
        'product_images': 'Upload product images for better catalog presentation.',
        'bulk_operations': 'Perform bulk actions on multiple products at once.',
        'csv_import_export': 'Import/export products via CSV for bulk management.',
      },
      'customers': {
        'customer_management': 'Create and manage customer profiles with contact details.',
        'customer_history': 'View complete purchase history for each customer.',
        'customer_reports': 'Generate customer behavior and purchase pattern reports.',
        'barcode_check': 'Scan customer barcodes for quick lookup during sales.',
        'qr_code_check': 'Use QR codes for customer identification and loyalty programs.',
      },
      'sales': {
        'pos': 'Fast cash-based transactions for walk-in customers.',
        'normal_sale': 'Full sales with invoicing, payment tracking, and installments.',
        'sales_history': 'Complete records of all sales with search and filtering.',
        'receipt_printing': 'Print receipts with customizable formats.',
      },
      'invoicing': {
        'invoice_creation': 'Create professional invoices from sales automatically.',
        'invoice_tracking': 'Monitor invoice status (draft, sent, partial, paid, overdue).',
        'payment_tracking': 'Track all payments against invoices.',
        'partial_payments': 'Allow multiple payments over time until fully paid.',
        'invoice_reports': 'Reports on invoice status, balances, and payment trends.',
      },
      'inventory': {
        'stock_adjustments': 'Manually adjust stock for corrections or counts.',
        'stock_transfers': 'Move stock between locations or branches.',
        'low_stock_alerts': 'Automatic notifications when stock is low.',
        'reorder_points': 'Set minimum stock levels to trigger reorder alerts.',
        'inventory_reports': 'Detailed reports on stock levels, movements, and valuation.',
      },
      'stock': {
        'manage_stock': 'Core stock management - track quantities and levels.',
        'stock_adjustments': 'Adjust stock for corrections, damage, or reconciliation.',
        'stock_transfers': 'Transfer stock between warehouses or branches.',
        'stock_reports': 'Comprehensive stock reports with history and valuation.',
        'low_stock_alerts': 'Automatic warnings when products reach low stock.',
      },
      'barcodes': {
        'barcode_generation': 'Generate standard barcodes (EAN-13, UPC-A, Code 128).',
        'qr_generation': 'Create QR codes for smartphone scanning.',
        'label_printing': 'Print barcode/QR labels for product labeling.',
        'bulk_generation': 'Generate codes for multiple products at once.',
      },
      'reports': {
        'sales_reports': 'Sales performance, revenue, trends, and top products.',
        'product_reports': 'Product performance, sales volume, and profitability.',
        'inventory_reports': 'Stock levels, valuation, and movement patterns.',
        'financial_reports': 'Profit/loss, revenue analysis, and expense breakdown.',
      },
      'accounting': {
        'chart_of_accounts': 'Organize accounts (assets, liabilities, equity, income, expenses).',
        'journal_entries': 'Record transactions with double-entry bookkeeping.',
        'balance_sheet': 'Financial position with assets, liabilities, and equity.',
        'income_statement': 'Profit & loss showing revenue, expenses, and net income.',
        'trial_balance': 'Verify accounting entries are balanced (debits = credits).',
        'general_ledger': 'Detailed ledger accounts with transaction history.',
      },
      'settings': {
        'user_management': 'Create and manage user accounts with role assignments.',
        'role_management': 'Define roles (admin, cashier, manager) with permissions.',
        'permission_management': 'Set granular permissions for actions and modules.',
        'module_settings': 'Enable/disable modules and features (this page).',
        'system_configuration': 'System-wide settings: business info, currency, tax rates.',
        'multi_branch_support': 'Enable multi-branch functionality. Branches are optional - disabled by default.',
      },
    };
    return featureTips[moduleName]?.[featureKey] || 'Feature functionality and settings';
  };

  const getModuleCategory = (moduleName) => {
    // Core Business Operations
    if (['products', 'sales', 'customers', 'invoicing', 'inventory', 'stock'].includes(moduleName)) {
      return 'Core Business Operations';
    }
    // Financial Management
    if (['expenses', 'income', 'bank_accounts', 'money_transfer'].includes(moduleName)) {
      return 'Financial Management';
    }
    // Accounting - All accounting items in one column
    if (['accounting', 'balance_sheet', 'trial_balance', 'cash_flow', 'account_statement'].includes(moduleName)) {
      return 'Accounting';
    }
    // General Reporting
    if (['reports'].includes(moduleName)) {
      return 'Reporting';
    }
    // Tools & Utilities
    if (['barcodes'].includes(moduleName)) {
      return 'Tools & Utilities';
    }
    // System Administration
    if (['settings'].includes(moduleName)) {
      return 'System Administration';
    }
    // Suppliers
    if (['suppliers'].includes(moduleName)) {
      return 'Supplier Management';
    }
    return 'Other';
  };

  const groupedModules = modules.reduce((acc, module) => {
    const category = getModuleCategory(module.module_name);
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(module);
    return acc;
  }, {});

  // Sort accounting modules: accounting first, then reports in specific order
  if (groupedModules['Accounting']) {
    const accountingOrder = ['accounting', 'balance_sheet', 'trial_balance', 'cash_flow', 'account_statement'];
    groupedModules['Accounting'].sort((a, b) => {
      const aIndex = accountingOrder.indexOf(a.module_name);
      const bIndex = accountingOrder.indexOf(b.module_name);
      if (aIndex === -1 && bIndex === -1) return 0;
      if (aIndex === -1) return 1;
      if (bIndex === -1) return -1;
      return aIndex - bIndex;
    });
  }

  const getEnabledFeaturesCount = (module) => {
    const features = Object.values(module.features || {});
    return features.filter(f => f.is_enabled).length;
  };

  const getTotalFeaturesCount = (module) => {
    return Object.keys(module.features || {}).length;
  };

  const getCategoryStatus = (categoryModules) => {
    const enabledCount = categoryModules.filter(m => m.is_enabled).length;
    const totalCount = categoryModules.length;
    return {
      enabledCount,
      totalCount,
      allEnabled: enabledCount === totalCount && totalCount > 0,
      someEnabled: enabledCount > 0 && enabledCount < totalCount,
      allDisabled: enabledCount === 0
    };
  };

  const handleToggleCategory = async (category, categoryModules) => {
    if (!isSuperAdmin) {
      toast.error('Only super admins can modify module settings');
      return;
    }

    const categoryStatus = getCategoryStatus(categoryModules);
    const shouldEnable = !categoryStatus.allEnabled; // Enable if not all enabled
    
    // Confirm if disabling entire category
    if (!shouldEnable && categoryStatus.allEnabled) {
      const confirmed = window.confirm(
        `Are you sure you want to disable all modules in "${category}"? This will disable ${categoryModules.length} module(s) and all their features.`
      );
      if (!confirmed) {
        return;
      }
    }

    // Update all modules in the category
    const updatePromises = categoryModules.map(async (module) => {
      if (module.is_enabled !== shouldEnable) {
        setSaving(prev => ({ ...prev, [module.id]: true }));
        try {
          const updatedModule = {
            ...module,
            is_enabled: shouldEnable,
          };
          
          await modulesAPI.update(module.id, updatedModule);
          
          // If disabling, disable all features
          if (!shouldEnable) {
            const features = Object.values(module.features || {});
            await Promise.all(
              features.map(feature => {
                const updatedFeature = { ...feature, is_enabled: false };
                return moduleFeaturesAPI.update(feature.id, updatedFeature);
              })
            );
          }
          
          return { module, success: true };
        } catch (error) {
          console.error(`Error updating module ${module.module_name}:`, error);
          return { module, success: false, error };
        } finally {
          setSaving(prev => ({ ...prev, [module.id]: false }));
        }
      }
      return { module, success: true, skipped: true };
    });

    const results = await Promise.all(updatePromises);
    const successCount = results.filter(r => r.success && !r.skipped).length;
    const errorCount = results.filter(r => !r.success).length;

    if (errorCount > 0) {
      toast.error(`Failed to update ${errorCount} module(s)`);
    } else if (successCount > 0) {
      toast.success(`${shouldEnable ? 'Enabled' : 'Disabled'} ${successCount} module(s) in ${category}`);
      loadModules(); // Reload to refresh state
    }
  };

  return (
    <Layout>
      <div className="module-settings-container">
        <div className="module-settings-header">
          <div>
            <h1>Module Settings</h1>
            <p>
              Enable or disable modules and their individual features. Only super admins can modify these settings.
              {isSuperAdmin && (
                <span style={{ 
                  display: 'inline-block', 
                  marginLeft: '0.5rem', 
                  padding: '0.25rem 0.75rem', 
                  background: '#d1fae5', 
                  color: '#065f46', 
                  borderRadius: '4px', 
                  fontSize: '0.875rem',
                  fontWeight: 600
                }}>
                  ✓ Super Admin Access
                </span>
              )}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading module settings...</div>
        ) : (
          <div className="module-settings-content">
            {Object.keys(groupedModules).map(category => {
              const categoryModules = groupedModules[category];
              const categoryStatus = getCategoryStatus(categoryModules);
              
              return (
                <div key={category} className="module-category" data-category={category}>
                  <div className="category-header">
                    <h2 className="category-title">{category}</h2>
                    <div className="category-actions">
                      <span className="category-status-badge">
                        {categoryStatus.enabledCount}/{categoryStatus.totalCount} enabled
                      </span>
                      <label className="toggle-switch large">
                        <input
                          type="checkbox"
                          checked={categoryStatus.allEnabled}
                          onChange={() => handleToggleCategory(category, categoryModules)}
                          disabled={categoryModules.some(m => saving[m.id]) || !isSuperAdmin || categoryModules.length === 0}
                          title={!isSuperAdmin ? 'Only super admins can modify modules' : categoryStatus.allEnabled ? 'Disable all modules in this category' : 'Enable all modules in this category'}
                        />
                        <span className="toggle-slider"></span>
                      </label>
                    </div>
                  </div>
                  <div className="modules-list">
                  {groupedModules[category].map(module => {
                    const features = Object.values(module.features || {});
                    const hasFeatures = features.length > 0;
                    const isExpanded = expandedModules[module.id];
                    const enabledFeaturesCount = getEnabledFeaturesCount(module);
                    const totalFeaturesCount = getTotalFeaturesCount(module);
                    
                    const isSettingsModule = module.module_name === 'settings';
                    
                    return (
                      <div key={module.id} className={`module-card ${module.is_enabled ? 'enabled' : 'disabled'} ${isSettingsModule ? 'settings-module' : ''}`}>
                        <div className="module-card-main">
                          <div className="module-card-header">
                            <div className="module-icon">{getModuleIcon(module.module_name)}</div>
                            <div className="module-info">
                              <div className="module-title-row">
                                <h3>
                                  {module.module_name_display}
                                  {isSettingsModule && (
                                    <span style={{ 
                                      marginLeft: '0.5rem', 
                                      padding: '0.125rem 0.5rem', 
                                      background: '#fef3c7', 
                                      color: '#92400e', 
                                      borderRadius: '4px', 
                                      fontSize: '0.75rem',
                                      fontWeight: 600
                                    }}>
                                      Critical
                                    </span>
                                  )}
                                </h3>
                                {hasFeatures && (
                                  <span className="feature-count-badge">
                                    {enabledFeaturesCount}/{totalFeaturesCount} features enabled
                                  </span>
                                )}
                              </div>
                              {isSettingsModule && module.is_enabled && (
                                <div style={{ 
                                  marginTop: '0.25rem', 
                                  padding: '0.25rem 0.5rem',
                                  background: '#fef3c7',
                                  borderRadius: '3px',
                                  fontSize: '0.6875rem', 
                                  color: '#92400e',
                                  border: '1px solid #fcd34d'
                                }}>
                                  ⚠️ Critical
                                </div>
                              )}
                            </div>
                          </div>
                          
                          <div className="module-actions">
                            <label className="toggle-switch large">
                              <input
                                type="checkbox"
                                checked={module.is_enabled}
                                onChange={() => handleToggleModule(module)}
                                disabled={saving[module.id] || !isSuperAdmin}
                                title={!isSuperAdmin ? 'Only super admins can modify modules' : ''}
                              />
                              <span className="toggle-slider"></span>
                            </label>
                            {hasFeatures && (
                              <button
                                className="expand-button"
                                onClick={() => toggleModuleExpansion(module.id)}
                                aria-label={isExpanded ? 'Collapse' : 'Expand'}
                              >
                                <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▼</span>
                              </button>
                            )}
                          </div>
                        </div>
                        
                        {hasFeatures && isExpanded && (
                          <div className={`module-features ${module.is_enabled ? '' : 'disabled-module'}`}>
                            <div className="features-header">
                              <h4 className="features-title">Features</h4>
                              {!module.is_enabled && (
                                <span className="features-disabled-notice">
                                  Enable the module to manage features
                                </span>
                              )}
                            </div>
                            <div className="features-list">
                              {features
                                .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
                                .map(feature => {
                                  const featureKey = feature.feature_key || Object.keys(module.features).find(k => module.features[k].id === feature.id);
                                  return (
                                    <div key={feature.id} className={`feature-item ${!feature.is_enabled ? 'feature-disabled' : ''}`}>
                                      <div className="feature-info">
                                        <div className="feature-name-row">
                                          <span className="feature-name">{feature.feature_name}</span>
                                          <span className={`feature-status ${feature.is_enabled ? 'enabled' : 'disabled'}`}>
                                            {feature.is_enabled ? 'Enabled' : 'Disabled'}
                                          </span>
                                        </div>
                                        <div className="feature-description-container">
                                          {feature.description && (
                                            <span className="feature-description">{feature.description}</span>
                                          )}
                                          <div className="feature-tip" title="How this feature works and what it enables">
                                            <span className="tip-icon">💡</span>
                                            <span className="tip-text">{getFeatureTips(module.module_name, featureKey)}</span>
                                          </div>
                                        </div>
                                      </div>
                                      <label className={`toggle-switch ${module.is_enabled && isSuperAdmin ? '' : 'disabled'}`}>
                                        <input
                                          type="checkbox"
                                          checked={feature.is_enabled}
                                          onChange={() => handleToggleFeature(module, featureKey)}
                                          disabled={saving[`feature-${feature.id}`] || !module.is_enabled || !isSuperAdmin}
                                          title={!isSuperAdmin ? 'Only super admins can modify features' : !module.is_enabled ? 'Enable the module first' : ''}
                                        />
                                        <span className="toggle-slider"></span>
                                      </label>
                                    </div>
                                  );
                                })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ModuleSettings;
