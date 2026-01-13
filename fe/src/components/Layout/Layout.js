import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authAPI, modulesAPI } from '../../services/api';
import BranchSelector from '../BranchSelector/BranchSelector';
import '../../styles/responsive.css';
import '../../styles/transitions.css';
import './Layout.css';

const Layout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  // Mobile-first: sidebar closed on mobile, open on desktop
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [moduleSettings, setModuleSettings] = useState({});
  const [loadingModules, setLoadingModules] = useState(true);
  const [expandedSections, setExpandedSections] = useState({
    main: false,
    inventory: true,
    stock: false,
    sales: false,
    customers: false,
    invoicing: false,
    reports: false,
    accounting: false,
    settings: false,
  });

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userProfile = user.profile || {};
  const isSuperAdmin = userProfile.role === 'super_admin' || user.is_superuser || userProfile.is_super_admin;
  const isAdmin = userProfile.role === 'admin' || isSuperAdmin;
  
  // Debug logging for module settings visibility
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      const settingsModule = moduleSettings['settings'];
      const moduleSettingsFeature = settingsModule?.features?.module_settings;
      
      console.log('Module Settings Visibility Check:', {
        user: user.username,
        role: userProfile.role,
        is_superuser: user.is_superuser,
        is_super_admin: userProfile.is_super_admin,
        isSuperAdmin,
        settingsModuleEnabled: settingsModule?.is_enabled,
        moduleSettingsFeatureEnabled: moduleSettingsFeature?.is_enabled,
        moduleSettingsFeatureExists: !!moduleSettingsFeature,
        willShow: isSuperAdmin && settingsModule?.is_enabled && moduleSettingsFeature?.is_enabled
      });
    }
  }, [user, userProfile, isSuperAdmin, moduleSettings]);
  
  // Try to get enabled modules from localStorage first (from login), then load from API
  const cachedModules = JSON.parse(localStorage.getItem('enabled_modules') || '{}');

  useEffect(() => {
    loadModuleSettings();
  }, []);

  const loadModuleSettings = async () => {
    try {
      const response = await modulesAPI.list();
      const modulesData = response.data || {};
      setModuleSettings(modulesData);
      // Update localStorage cache
      localStorage.setItem('enabled_modules', JSON.stringify(modulesData));
    } catch (error) {
      console.error('Error loading module settings:', error);
      // Fallback to cached modules or default to all enabled
      if (Object.keys(cachedModules).length > 0) {
        setModuleSettings(cachedModules);
      } else {
        setModuleSettings({});
      }
    } finally {
      setLoadingModules(false);
    }
  };

  const isModuleEnabled = (moduleName) => {
    if (loadingModules) return true; // Show while loading
    if (!moduleSettings || Object.keys(moduleSettings).length === 0) {
      return true; // Default to enabled if not loaded yet
    }
    const module = moduleSettings[moduleName];
    return module ? module.is_enabled : true; // Default to enabled if not configured
  };

  const isFeatureEnabled = (moduleName, featureKey) => {
    if (loadingModules) return true; // Show while loading
    if (!moduleSettings || Object.keys(moduleSettings).length === 0) {
      return true; // Default to enabled if not loaded yet
    }
    const module = moduleSettings[moduleName];
    if (!module || !module.is_enabled) {
      return false; // Module must be enabled first
    }
    const features = module.features || {};
    const feature = features[featureKey];
    // If feature doesn't exist, default to enabled (for backward compatibility)
    // If feature exists, check its is_enabled status
    return feature ? feature.is_enabled : true;
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleLogout = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        await authAPI.logout(refreshToken);
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('isAuthenticated');
      localStorage.removeItem('user');
      localStorage.removeItem('enabled_modules');
      navigate('/login');
    }
  };

  const isActive = (path) => {
    return location.pathname === path;
  };

  // Handle window resize for responsive sidebar
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setSidebarOpen(true);
      } else if (window.innerWidth < 640) {
        // Keep current state on tablet, close on mobile
        if (window.innerWidth < 640) {
          setSidebarOpen(false);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Close sidebar when clicking outside on mobile/tablet
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (window.innerWidth < 1024 && sidebarOpen) {
        if (!e.target.closest('.sidebar') && !e.target.closest('.menu-toggle')) {
          setSidebarOpen(false);
        }
      }
    };

    if (sidebarOpen && window.innerWidth < 1024) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [sidebarOpen]);

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 1024;

  return (
    <div className="app-layout">
      {/* Sidebar overlay for mobile/tablet */}
      {isMobile && sidebarOpen && (
        <div 
          className="sidebar-overlay active"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close sidebar"
        />
      )}
      {/* Top Header */}
      <header className="app-header">
        <div className="header-left">
          <button className="menu-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            ☰
          </button>
          <div className="logo">CompleteByte POS</div>
        </div>
        <div className="header-right">
          <BranchSelector showAllOption={isSuperAdmin} />
          <div className="user-profile" onClick={() => setShowUserMenu(!showUserMenu)}>
            <div className="user-avatar">{user.username?.[0]?.toUpperCase() || 'U'}</div>
            <span>{user.username || 'Admin'}</span>
            <span className="dropdown-arrow">▼</span>
            {showUserMenu && (
              <div className="user-menu">
                <div className="menu-item">My Profile</div>
                <div className="menu-item">Settings</div>
                <div className="menu-divider"></div>
                <div className="menu-item" onClick={handleLogout}>Logout</div>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="app-body">
        {/* Left Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? 'open' : ''} ${!isMobile && !sidebarOpen ? 'closed' : ''}`}>
          <div className="sidebar-content">
            {/* Main Section */}
            <div className="sidebar-section">
              <div className="section-header" onClick={() => toggleSection('main')}>
                <span>Main</span>
                <span className="section-arrow">{expandedSections.main ? '▼' : '▶'}</span>
              </div>
              {expandedSections.main && (
                <div className="section-items">
                  <Link to="/" className={`sidebar-item ${isActive('/') ? 'active' : ''}`}>
                    <span className="item-icon">📊</span>
                    <span>Dashboard</span>
                  </Link>
                </div>
              )}
            </div>

            {/* Inventory Section */}
            {isModuleEnabled('products') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('inventory')}>
                  <span>Inventory</span>
                  <span className="section-arrow">{expandedSections.inventory ? '▼' : '▶'}</span>
                </div>
                {expandedSections.inventory && (
                  <div className="section-items">
                    <Link to="/products" className={`sidebar-item ${isActive('/products') ? 'active' : ''}`}>
                      <span className="item-icon">📦</span>
                      <span>Products</span>
                    </Link>
                    <Link to="/categories" className={`sidebar-item ${isActive('/categories') ? 'active' : ''}`}>
                      <span className="item-icon">📁</span>
                      <span>Category</span>
                    </Link>
                    {isModuleEnabled('barcodes') && (
                      <>
                        <Link to="/barcodes" className={`sidebar-item ${isActive('/barcodes') ? 'active' : ''}`}>
                          <span className="item-icon">🏷️</span>
                          <span>Print Barcode</span>
                        </Link>
                        <Link to="/barcodes" className={`sidebar-item ${isActive('/barcodes') ? 'active' : ''}`}>
                          <span className="item-icon">📱</span>
                          <span>Print QR Code</span>
                        </Link>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Stock Section */}
            {isModuleEnabled('stock') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('stock')}>
                  <span>Stock</span>
                  <span className="section-arrow">{expandedSections.stock ? '▼' : '▶'}</span>
                </div>
                {expandedSections.stock && (
                  <div className="section-items">
                    {isFeatureEnabled('stock', 'manage_stock') && (
                      <Link 
                        to="/inventory?view=movements" 
                        className={`sidebar-item ${isActive('/inventory') ? 'active' : ''}`}
                        onClick={() => {
                          // Close sidebar on mobile after navigation
                          if (window.innerWidth < 1024) {
                            setSidebarOpen(false);
                          }
                        }}
                      >
                        <span className="item-icon">📊</span>
                        <span>Manage Stock</span>
                      </Link>
                    )}
                    {isFeatureEnabled('stock', 'stock_adjustments') && (
                      <Link 
                        to="/inventory?action=adjust" 
                        className={`sidebar-item ${isActive('/inventory') ? 'active' : ''}`}
                        onClick={() => {
                          // Close sidebar on mobile after navigation
                          if (window.innerWidth < 1024) {
                            setSidebarOpen(false);
                          }
                        }}
                      >
                        <span className="item-icon">⚖️</span>
                        <span>Stock Adjustment</span>
                      </Link>
                    )}
                    {isFeatureEnabled('stock', 'stock_transfers') && (
                      <Link 
                        to="/inventory?action=transfer" 
                        className={`sidebar-item ${isActive('/inventory') ? 'active' : ''}`}
                        onClick={() => {
                          // Close sidebar on mobile after navigation
                          if (window.innerWidth < 1024) {
                            setSidebarOpen(false);
                          }
                        }}
                      >
                        <span className="item-icon">🔄</span>
                        <span>Stock Transfer</span>
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Sales Section - Updated with Customers and Invoicing */}
            {isModuleEnabled('sales') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('sales')}>
                  <span>Sales</span>
                  <span className="section-arrow">{expandedSections.sales ? '▼' : '▶'}</span>
                </div>
                {expandedSections.sales && (
                  <div className="section-items">
                    {isFeatureEnabled('sales', 'pos') && (
                      <Link to="/pos" className={`sidebar-item ${isActive('/pos') ? 'active' : ''}`}>
                        <span className="item-icon">🛒</span>
                        <span>POS</span>
                      </Link>
                    )}
                    {isFeatureEnabled('sales', 'normal_sale') && (
                      <Link to="/normal-sale" className={`sidebar-item ${isActive('/normal-sale') ? 'active' : ''}`}>
                        <span className="item-icon">💼</span>
                        <span>Normal Sale</span>
                      </Link>
                    )}
                    {isFeatureEnabled('sales', 'sales_history') && (
                      <Link to="/sales" className={`sidebar-item ${isActive('/sales') ? 'active' : ''}`}>
                        <span className="item-icon">💰</span>
                        <span>Sales History</span>
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}
            
            {/* Customers Section */}
            {isModuleEnabled('customers') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('customers')}>
                  <span>Customers</span>
                  <span className="section-arrow">{expandedSections.customers ? '▼' : '▶'}</span>
                </div>
                {expandedSections.customers && (
                  <div className="section-items">
                    <Link to="/customers" className={`sidebar-item ${isActive('/customers') ? 'active' : ''}`}>
                      <span className="item-icon">👥</span>
                      <span>Customers</span>
                    </Link>
                  </div>
                )}
              </div>
            )}
            
            {/* Invoicing Section */}
            {isModuleEnabled('invoicing') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('invoicing')}>
                  <span>Invoicing</span>
                  <span className="section-arrow">{expandedSections.invoicing ? '▼' : '▶'}</span>
                </div>
                {expandedSections.invoicing && (
                  <div className="section-items">
                    <Link to="/invoices" className={`sidebar-item ${isActive('/invoices') ? 'active' : ''}`}>
                      <span className="item-icon">📄</span>
                      <span>Invoices</span>
                    </Link>
                  </div>
                )}
              </div>
            )}

            {/* Reports Section */}
            {isModuleEnabled('reports') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('reports')}>
                  <span>Reports</span>
                  <span className="section-arrow">{expandedSections.reports ? '▼' : '▶'}</span>
                </div>
                {expandedSections.reports && (
                  <div className="section-items">
                    <Link 
                      to="/reports?report=sales" 
                      className={`sidebar-item ${isActive('/reports') && location.search.includes('report=sales') ? 'active' : ''}`}
                    >
                      <span className="item-icon">📊</span>
                      <span>Sales Summary</span>
                    </Link>
                    <Link 
                      to="/reports?report=sales-by-method" 
                      className={`sidebar-item ${isActive('/reports') && location.search.includes('report=sales-by-method') ? 'active' : ''}`}
                    >
                      <span className="item-icon">💳</span>
                      <span>Sales by Payment</span>
                    </Link>
                    <Link 
                      to="/reports?report=daily-sales" 
                      className={`sidebar-item ${isActive('/reports') && location.search.includes('report=daily-sales') ? 'active' : ''}`}
                    >
                      <span className="item-icon">📅</span>
                      <span>Daily Sales</span>
                    </Link>
                    <Link 
                      to="/reports?report=products" 
                      className={`sidebar-item ${isActive('/reports') && location.search.includes('report=products') ? 'active' : ''}`}
                    >
                      <span className="item-icon">📦</span>
                      <span>Product Performance</span>
                    </Link>
                    <Link 
                      to="/reports?report=inventory" 
                      className={`sidebar-item ${isActive('/reports') && location.search.includes('report=inventory') ? 'active' : ''}`}
                    >
                      <span className="item-icon">📋</span>
                      <span>Inventory Overview</span>
                    </Link>
                  </div>
                )}
              </div>
            )}

            {/* Accounting Section */}
            {isModuleEnabled('accounting') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('accounting')}>
                  <span>Finance & Accounts</span>
                  <span className="section-arrow">{expandedSections.accounting ? '▼' : '▶'}</span>
                </div>
                {expandedSections.accounting && (
                  <div className="section-items">
                    <Link to="/accounting" className={`sidebar-item ${isActive('/accounting') ? 'active' : ''}`}>
                      <span className="item-icon">📊</span>
                      <span>Accounting</span>
                    </Link>
                    {isModuleEnabled('expenses') && (
                      <Link to="/expenses" className={`sidebar-item ${isActive('/expenses') ? 'active' : ''}`}>
                        <span className="item-icon">💸</span>
                        <span>Expenses</span>
                      </Link>
                    )}
                    {isModuleEnabled('income') && (
                      <Link to="/income" className={`sidebar-item ${isActive('/income') ? 'active' : ''}`}>
                        <span className="item-icon">💰</span>
                        <span>Income</span>
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Settings Section */}
            {isModuleEnabled('settings') && (
              <div className="sidebar-section">
                <div className="section-header" onClick={() => toggleSection('settings')}>
                  <span>Settings</span>
                  <span className="section-arrow">{expandedSections.settings ? '▼' : '▶'}</span>
                </div>
                {expandedSections.settings && (
                  <div className="section-items">
                    {isFeatureEnabled('settings', 'user_management') && (
                      <Link to="/users" className={`sidebar-item ${isActive('/users') ? 'active' : ''}`}>
                        <span className="item-icon">👥</span>
                        <span>User Management</span>
                      </Link>
                    )}
                    {isFeatureEnabled('settings', 'role_management') && (
                      <Link to="/roles" className={`sidebar-item ${isActive('/roles') ? 'active' : ''}`}>
                        <span className="item-icon">🔐</span>
                        <span>Role Management</span>
                      </Link>
                    )}
                    {isSuperAdmin && (isFeatureEnabled('settings', 'module_settings') || isModuleEnabled('settings')) && (
                      <Link to="/module-settings" className={`sidebar-item ${isActive('/module-settings') ? 'active' : ''}`}>
                        <span className="item-icon">⚙️</span>
                        <span>Module Settings</span>
                      </Link>
                    )}
                    {isSuperAdmin && (
                      <Link to="/branches" className={`sidebar-item ${isActive('/branches') ? 'active' : ''}`}>
                        <span className="item-icon">🏢</span>
                        <span>Branch Management</span>
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;

