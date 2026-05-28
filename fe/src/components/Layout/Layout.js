import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Menu,
  ChevronDown,
  LogOut,
  Settings,
  User as UserIcon,
  LayoutDashboard,
  Package,
  FolderTree,
  Barcode,
  QrCode,
  BarChart3,
  Scale,
  ArrowLeftRight,
  Factory,
  ShoppingCart,
  Briefcase,
  DollarSign,
  Users as UsersIcon,
  FileText,
  CreditCard,
  Calendar,
  Boxes,
  PieChart,
  Receipt,
  TrendingDown,
  TrendingUp,
  ShieldCheck,
  KeyRound,
  Building2,
  Calculator,
} from 'lucide-react';

import { authAPI, modulesAPI } from '../../services/api';
import BranchSelector from '../BranchSelector/BranchSelector';
import { Button } from '../ui/button';
import { Separator } from '../ui/separator';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { cn } from '../../lib/cn';
import { canSeeNavItem, buildNavContext } from '../../utils/navAccess';
import { normalizeModuleSettings } from '../../utils/moduleCache';

/**
 * Navigation tree.
 *
 * Defined once, rendered everywhere — replaces the old approach of writing
 * each link twice (once for the inline sidebar and once for the hover popout).
 * Visibility is computed at render time via the module-settings predicates,
 * so adding/removing a section is now a one-line change in this array.
 *
 * Each entry:
 *  - `id`      — used as the expand/hover state key
 *  - `label`   — section header
 *  - `module`  — backend module name; section hidden when module disabled
 *  - `items`   — leaf links. Optional `feature` is checked against module
 *                feature flags. Optional `requireSuperAdmin` gates by role.
 */
const NAV_SECTIONS = [
  {
    id: 'main',
    label: 'Main',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    id: 'sales',
    label: 'Sales',
    module: 'sales',
    items: [
      { to: '/pos', label: 'POS', icon: ShoppingCart, feature: ['sales', 'pos'] },
      { to: '/pos/billing', label: 'Billing', icon: Receipt, feature: ['sales', 'billing_pos'] },
      { to: '/normal-sale', label: 'Normal Sale', icon: Briefcase, feature: ['sales', 'normal_sale'] },
      { to: '/sales', label: 'Sales History', icon: DollarSign, feature: ['sales', 'sales_history'] },
    ],
  },
  {
    id: 'customers',
    label: 'Customers',
    module: 'customers',
    items: [
      { to: '/customers', label: 'Customers', icon: UsersIcon },
    ],
  },
  {
    id: 'inventory',
    label: 'Inventory',
    module: 'products',
    items: [
      { to: '/products', label: 'Products', icon: Package },
      { to: '/categories', label: 'Categories', icon: FolderTree },
      { to: '/barcodes', label: 'Print Barcode', icon: Barcode, module: 'barcodes' },
      { to: '/barcodes', label: 'Print QR Code', icon: QrCode, module: 'barcodes' },
    ],
  },
  {
    id: 'stock',
    label: 'Stock',
    module: 'stock',
    items: [
      { to: '/inventory?view=movements', label: 'Manage Stock', icon: BarChart3, feature: ['stock', 'manage_stock'] },
      { to: '/inventory?action=adjust', label: 'Stock Adjustment', icon: Scale, feature: ['stock', 'stock_adjustments'] },
      { to: '/inventory?action=transfer', label: 'Stock Transfer', icon: ArrowLeftRight, feature: ['stock', 'stock_transfers'] },
    ],
  },
  {
    id: 'suppliers',
    label: 'Suppliers',
    module: 'suppliers',
    items: [
      { to: '/suppliers', label: 'Suppliers', icon: Factory },
    ],
  },
  {
    id: 'invoicing',
    label: 'Invoicing',
    module: 'invoicing',
    items: [
      { to: '/invoices', label: 'Invoices', icon: FileText },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    module: 'reports',
    items: [
      { to: '/reports?report=sales', label: 'Sales Summary', icon: BarChart3, match: 'report=sales' },
      { to: '/reports?report=sales-by-method', label: 'Sales by Payment', icon: CreditCard, match: 'report=sales-by-method' },
      { to: '/reports?report=daily-sales', label: 'Daily Sales', icon: Calendar, match: 'report=daily-sales' },
      { to: '/reports?report=products', label: 'Product Performance', icon: Boxes, match: 'report=products' },
      { to: '/reports?report=inventory', label: 'Inventory Overview', icon: PieChart, match: 'report=inventory' },
    ],
  },
  {
    id: 'accounting',
    label: 'Finance & Accounts',
    module: 'accounting',
    items: [
      { to: '/accounting', label: 'Accounting', icon: Calculator },
      { to: '/expenses', label: 'Expenses', icon: TrendingDown, module: 'expenses' },
      { to: '/income', label: 'Income', icon: TrendingUp, module: 'income' },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    module: 'settings',
    items: [
      { to: '/users', label: 'User Management', icon: UsersIcon, feature: ['settings', 'user_management'] },
      { to: '/roles', label: 'Role Management', icon: ShieldCheck, feature: ['settings', 'role_management'] },
      { to: '/module-settings', label: 'Module Settings', icon: KeyRound, requireSuperAdmin: true },
      { to: '/branches', label: 'Branch Management', icon: Building2, requireSuperAdmin: true },
    ],
  },
];

const Layout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth >= 1024
  );
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth < 1024
  );
  const [moduleSettings, setModuleSettings] = useState({});
  const [loadingModules, setLoadingModules] = useState(true);
  // Initially everything collapsed except the most-used section to reduce
  // visual noise. Cashiers can pop sections open as they need them.
  const [expanded, setExpanded] = useState({ sales: true, inventory: true });

  // Read user once per mount, not on every render (the original re-parsed the
  // localStorage JSON on every commit which broke dependency arrays). Stable
  // identity = stable hook deps.
  const user = useMemo(
    () => JSON.parse(localStorage.getItem('user') || '{}'),
    []
  );
  const userProfile = useMemo(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('profile') || 'null');
      return stored || user.profile || {};
    } catch {
      return user.profile || {};
    }
  }, [user]);
  const isSuperAdmin =
    user?.is_superuser ||
    userProfile.role === 'super_admin' ||
    userProfile.is_super_admin ||
    userProfile.custom_role?.name === 'Super Admin';

  const loadModuleSettings = useCallback(async () => {
    try {
      const response = await modulesAPI.list();
      const flat = normalizeModuleSettings(response.data || {});
      setModuleSettings(flat);
      localStorage.setItem('enabled_modules', JSON.stringify(flat));
    } catch (error) {
      const cached = normalizeModuleSettings(
        JSON.parse(localStorage.getItem('enabled_modules') || '{}')
      );
      setModuleSettings(cached);
    } finally {
      setLoadingModules(false);
    }
  }, []);

  useEffect(() => {
    loadModuleSettings();
  }, [loadModuleSettings]);

  useEffect(() => {
    const onModulesUpdated = (event) => {
      const flat = normalizeModuleSettings(event.detail || {});
      setModuleSettings(flat);
      setLoadingModules(false);
    };
    window.addEventListener('moduleSettingsUpdated', onModulesUpdated);
    return () => window.removeEventListener('moduleSettingsUpdated', onModulesUpdated);
  }, []);

  // Keep sidebar in sync with viewport size. < 1024 px = mobile; sidebar is
  // a drawer that overlays content. >= 1024 px = desktop; sidebar is pinned.
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      setSidebarOpen(!mobile);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const normalizedModules = useMemo(
    () => normalizeModuleSettings(moduleSettings),
    [moduleSettings]
  );

  const isModuleEnabled = useCallback(
    (moduleName) => {
      if (isSuperAdmin) return true;
      if (!moduleName) return true;
      if (loadingModules) return true;
      if (!normalizedModules || Object.keys(normalizedModules).length === 0) return true;
      const module = normalizedModules[moduleName];
      if (module == null) return true;
      return Boolean(module.is_enabled);
    },
    [loadingModules, normalizedModules, isSuperAdmin]
  );

  const isFeatureEnabled = useCallback(
    (moduleName, featureKey) => {
      if (isSuperAdmin) return true;
      if (loadingModules) return true;
      const module = normalizedModules[moduleName];
      if (!module || !module.is_enabled) return false;
      const feature = (module.features || {})[featureKey];
      return feature ? Boolean(feature.is_enabled) : true;
    },
    [loadingModules, normalizedModules, isSuperAdmin]
  );

  const navCtx = useMemo(
    () => buildNavContext(moduleSettings, loadingModules),
    [moduleSettings, loadingModules]
  );

  const itemVisible = useCallback(
    (item, sectionId) => canSeeNavItem(item, sectionId, navCtx),
    [navCtx]
  );

  const isActive = useCallback(
    (item) => {
      if (item.match) {
        return location.pathname.startsWith(item.to.split('?')[0]) &&
          location.search.includes(item.match);
      }
      // Strip query string for plain matches so `/inventory?view=movements`
      // and `/inventory` both count as active on /inventory.
      const path = item.to.split('?')[0];
      return location.pathname === path;
    },
    [location]
  );

  const toggleSection = (id) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleLogout = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) await authAPI.logout(refreshToken);
    } catch (e) {
      // Logout endpoint failure shouldn't trap the user in the app.
    } finally {
      ['access_token', 'refresh_token', 'isAuthenticated', 'user', 'enabled_modules']
        .forEach((key) => localStorage.removeItem(key));
      navigate('/login');
    }
  };

  const handleNavClick = () => {
    // Collapse the drawer after a navigation on mobile/tablet.
    if (isMobile) setSidebarOpen(false);
  };

  // Filter out empty sections (module off, all items hidden) so we don't
  // render a meaningless collapsed header.
  const visibleSections = useMemo(
    () =>
      NAV_SECTIONS.map((section) => ({
        ...section,
        visibleItems: section.items.filter((item) => itemVisible(item, section.id)),
      }))
        .filter(
          (section) =>
            (!section.module || isModuleEnabled(section.module)) &&
            section.visibleItems.length > 0
        ),
    [itemVisible, isModuleEnabled]
  );

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Top bar */}
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background px-3 sm:px-4">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={() => setSidebarOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <Link to="/" className="flex items-center gap-2">
          <img src="/logo.svg" alt="CompleteByte POS" className="h-7 w-auto" />
          <span className="hidden text-sm font-semibold text-foreground sm:inline">
            CompleteByte POS
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <BranchSelector showAllOption={isSuperAdmin} />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="flex h-10 items-center gap-2 px-2"
                aria-label="User menu"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">
                  {user.username?.[0]?.toUpperCase() || 'U'}
                </span>
                <span className="hidden text-sm font-medium sm:inline">
                  {user.username || 'Admin'}
                </span>
                <ChevronDown className="hidden h-4 w-4 text-muted-foreground sm:inline" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="flex flex-col">
                <span>{user.username || 'Admin'}</span>
                {user.email && (
                  <span className="text-xs font-normal text-muted-foreground">{user.email}</span>
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled>
                <UserIcon className="h-4 w-4" />
                My Profile
              </DropdownMenuItem>
              <DropdownMenuItem disabled>
                <Settings className="h-4 w-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                <LogOut className="h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Backdrop for mobile drawer */}
        {isMobile && sidebarOpen && (
          <div
            className="fixed inset-0 top-14 z-30 bg-black/40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Sidebar */}
        <aside
          className={cn(
            'fixed inset-y-14 left-0 z-30 w-64 shrink-0 overflow-y-auto border-r bg-background transition-transform duration-200 lg:static lg:inset-auto lg:translate-x-0',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          )}
          aria-label="Primary navigation"
        >
          <nav className="flex flex-col gap-1 p-3">
            {visibleSections.map((section, idx) => (
              <NavSection
                key={section.id}
                section={section}
                expanded={!!expanded[section.id]}
                onToggle={() => toggleSection(section.id)}
                isActive={isActive}
                onNavigate={handleNavClick}
                showDivider={idx < visibleSections.length - 1}
              />
            ))}
          </nav>
        </aside>

        {/* Main content area */}
        <main className="app-surface flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};

const NavSection = ({ section, expanded, onToggle, isActive, onNavigate, showDivider }) => (
  <div className="flex flex-col">
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        'flex h-10 items-center justify-between rounded-md px-3 text-sm font-semibold',
        'text-muted-foreground hover:bg-accent hover:text-foreground'
      )}
      aria-expanded={expanded}
    >
      <span>{section.label}</span>
      <ChevronDown
        className={cn(
          'h-4 w-4 transition-transform duration-150',
          expanded ? 'rotate-0' : '-rotate-90'
        )}
      />
    </button>

    {expanded && (
      <div className="mt-1 flex flex-col gap-0.5">
        {section.visibleItems.map((item) => (
          <NavItem key={`${section.id}-${item.to}-${item.label}`} item={item} isActive={isActive} onNavigate={onNavigate} />
        ))}
      </div>
    )}

    {showDivider && <Separator className="my-2" />}
  </div>
);

const NavItem = ({ item, isActive, onNavigate }) => {
  const Icon = item.icon;
  const active = isActive(item);
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      className={cn(
        'pos-target flex items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors',
        active
          ? 'bg-primary/10 text-primary'
          : 'text-foreground/80 hover:bg-accent hover:text-foreground'
      )}
      aria-current={active ? 'page' : undefined}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0" />}
      <span className="truncate">{item.label}</span>
    </Link>
  );
};

export default Layout;
