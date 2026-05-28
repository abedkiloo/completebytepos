import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  LayoutDashboard,
  ShoppingCart,
  Receipt,
  Package,
  BarChart3,
  Users,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
} from 'lucide-react';
import { reportsAPI, productsAPI, salesAPI, authAPI } from '../../services/api';
import { formatCurrency, formatNumber } from '../../utils/formatters';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { cn } from '../../lib/cn';
import { PageShell } from '../page';

function resolvePersona(me) {
  const profile = me?.profile;
  const role = profile?.role;
  const customName = profile?.custom_role?.name;
  if (me?.is_super_admin || role === 'super_admin' || customName === 'Super Admin') {
    return 'super_admin';
  }
  if (role === 'manager' || customName === 'Manager') {
    return 'manager';
  }
  return 'sales';
}

const QUICK_ACTIONS = {
  super_admin: [
    { to: '/pos', label: 'Retail POS', icon: ShoppingCart, description: 'Fast checkout' },
    { to: '/pos/billing', label: 'Billing POS', icon: Receipt, description: 'Invoices & holding' },
    { to: '/products', label: 'Products', icon: Package, description: 'Catalog & stock' },
    { to: '/reports', label: 'Reports', icon: BarChart3, description: 'Business insights' },
    { to: '/users', label: 'Users', icon: Users, description: 'Access control' },
    { to: '/module-settings', label: 'Modules', icon: LayoutDashboard, description: 'Feature toggles' },
  ],
  manager: [
    { to: '/pos', label: 'Retail POS', icon: ShoppingCart, description: 'Sell at counter' },
    { to: '/pos/billing', label: 'Billing POS', icon: Receipt, description: 'Credit & drafts' },
    { to: '/products', label: 'Products', icon: Package, description: 'Stock & pricing' },
    { to: '/inventory', label: 'Inventory', icon: Package, description: 'Purchases & moves' },
    { to: '/reports', label: 'Reports', icon: BarChart3, description: 'Sales & stock' },
    { to: '/customers', label: 'Customers', icon: Users, description: 'CRM' },
  ],
  sales: [
    { to: '/pos', label: 'Start sale', icon: ShoppingCart, description: 'Retail POS' },
    { to: '/pos/billing', label: 'Billing', icon: Receipt, description: 'Invoice checkout' },
    { to: '/customers', label: 'Customers', icon: Users, description: 'Walk-in & credit' },
  ],
};

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [recentSales, setRecentSales] = useState([]);
  const [me, setMe] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [meRes, dashRes, stockRes, salesRes] = await Promise.all([
          authAPI.me().catch(() => null),
          reportsAPI.dashboard().catch(() => null),
          productsAPI.list({ low_stock: 'true', is_active: 'true' }).catch(() => null),
          salesAPI.list({ limit: 6 }).catch(() => null),
        ]);
        if (meRes?.data) setMe(meRes.data);
        if (dashRes?.data) setDashboardData(dashRes.data);
        const products = stockRes?.data?.results || stockRes?.data || [];
        setLowStockProducts(Array.isArray(products) ? products.slice(0, 5) : []);
        const sales = salesRes?.data?.results || salesRes?.data || [];
        setRecentSales(Array.isArray(sales) ? sales.filter((s) => s.status !== 'holding').slice(0, 6) : []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const persona = useMemo(() => resolvePersona(me), [me]);
  const displayName = me?.user?.username || me?.user?.first_name || 'there';
  const roleLabel =
    me?.profile?.custom_role?.name || me?.profile?.role_display || 'Team member';

  const data = dashboardData || {
    today: { sales_count: 0, total: 0 },
    month: { total: 0 },
    low_stock_count: 0,
    total_sales: 0,
    profit: 0,
    growth: { sales: 0, profit: 0 },
    overall: { customers: 0, orders: 0 },
  };

  const kpis =
    persona === 'sales'
      ? [
          {
            label: "Today's sales",
            value: formatCurrency(data.today?.total || 0),
            hint: `${data.today?.sales_count || 0} orders`,
          },
          {
            label: 'This month',
            value: formatCurrency(data.month?.total || 0),
            hint: 'Completed sales',
          },
        ]
      : [
          {
            label: "Today's sales",
            value: formatCurrency(data.today?.total || 0),
            hint: `${data.today?.sales_count || 0} orders today`,
          },
          {
            label: 'Month revenue',
            value: formatCurrency(data.month?.total || data.total_sales || 0),
            hint: 'Completed sales',
          },
          {
            label: 'Profit (est.)',
            value: formatCurrency(data.profit || 0),
            hint: 'From dashboard report',
          },
          {
            label: 'Low stock SKUs',
            value: formatNumber(data.low_stock_count || lowStockProducts.length),
            hint: 'Needs attention',
            alert: (data.low_stock_count || lowStockProducts.length) > 0,
          },
        ];

  const actions = QUICK_ACTIONS[persona] || QUICK_ACTIONS.sales;

  if (loading) {
    return (
      <PageShell>
          <Skeleton className="h-10 w-64" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        </PageShell>
    );
  }

  return (
    <PageShell>
        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Welcome back</p>
            <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
              {displayName}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{roleLabel}</Badge>
              {data.today?.sales_count > 0 && (
                <span className="text-sm text-muted-foreground">
                  {data.today.sales_count} order{data.today.sales_count !== 1 ? 's' : ''} today
                </span>
              )}
            </div>
          </div>
          {persona !== 'sales' && lowStockProducts.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <span className="font-medium">{lowStockProducts[0].name}</span> is low (
                {formatNumber(lowStockProducts[0].stock_quantity)} left).{' '}
                <Link to="/products?low_stock=true" className="underline underline-offset-2">
                  Restock
                </Link>
              </div>
            </div>
          )}
        </header>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <Card
              key={kpi.label}
              className={cn(kpi.alert && 'border-amber-300 dark:border-amber-800')}
            >
              <CardHeader className="pb-2">
                <CardDescription>{kpi.label}</CardDescription>
                <CardTitle className="text-2xl font-bold tabular-nums">{kpi.value}</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-xs text-muted-foreground">{kpi.hint}</p>
              </CardContent>
            </Card>
          ))}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground uppercase tracking-wide">
            Quick actions
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {actions.map(({ to, label, icon: Icon, description }) => (
              <Link key={to} to={to} className="group block">
                <Card className="h-full transition-colors hover:border-primary/40 hover:bg-muted/30">
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium group-hover:text-primary">{label}</p>
                      <p className="text-sm text-muted-foreground">{description}</p>
                    </div>
                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">Recent sales</CardTitle>
                <CardDescription>Latest completed transactions</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/sales">View all</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {recentSales.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No sales yet.{' '}
                  <Link to="/pos" className="text-primary underline">
                    Open POS
                  </Link>
                </p>
              ) : (
                <ul className="divide-y">
                  {recentSales.map((sale) => (
                    <li
                      key={sale.id}
                      className="flex items-center justify-between gap-2 py-3 first:pt-0 last:pb-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-sm">
                          {sale.sale_number || `Sale #${sale.id}`}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {sale.created_at
                            ? new Date(sale.created_at).toLocaleString()
                            : '—'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold tabular-nums text-sm">
                          {formatCurrency(sale.total || 0)}
                        </p>
                        <Badge variant="outline" className="mt-1 text-xs capitalize">
                          {sale.status || 'completed'}
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {persona !== 'sales' && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Low stock</CardTitle>
                  <CardDescription>Products below threshold</CardDescription>
                </div>
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/products?low_stock=true">View all</Link>
                </Button>
              </CardHeader>
              <CardContent>
                {lowStockProducts.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    All products are adequately stocked.
                  </p>
                ) : (
                  <ul className="divide-y">
                    {lowStockProducts.map((product) => (
                      <li
                        key={product.id}
                        className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium text-sm">{product.name}</p>
                          <p className="text-xs text-muted-foreground">SKU {product.sku}</p>
                        </div>
                        <Badge variant="destructive" className="tabular-nums">
                          {formatNumber(product.stock_quantity)} left
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}

          {persona === 'sales' && data.growth?.sales !== undefined && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Your shift focus
                </CardTitle>
                <CardDescription>Keep checkout fast and accurate</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>Use <strong className="text-foreground">Retail POS</strong> for walk-in cash/card sales.</p>
                <p>Use <strong className="text-foreground">Billing POS</strong> for invoices, credit, and held carts.</p>
                <p>Search by name, SKU, or barcode — stock shows before you add to cart.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </PageShell>
  );
};

export default Dashboard;
