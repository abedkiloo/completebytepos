import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { reportsAPI, productsAPI, salesAPI, authAPI } from '../../services/api';
import { formatCurrency, formatNumber } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import './Dashboard.css';

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [recentSales, setRecentSales] = useState([]);
  const [topProducts, setTopProducts] = useState([]);
  const [timeFilter, setTimeFilter] = useState('1M');
  const [user, setUser] = useState(null);

  useEffect(() => {
    loadDashboard();
    loadLowStockProducts();
    loadRecentSales();
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const response = await authAPI.me();
      setUser(response.data);
    } catch (error) {
      console.error('Error loading user:', error);
      // Fallback to localStorage
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
    }
  };

  const loadDashboard = async () => {
    try {
      const response = await reportsAPI.dashboard();
      setDashboardData(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
      setDashboardData(null);
    } finally {
      setLoading(false);
    }
  };

  const loadLowStockProducts = async () => {
    try {
      const response = await productsAPI.list({ low_stock: 'true', is_active: 'true' });
      const products = response.data.results || response.data || [];
      setLowStockProducts(Array.isArray(products) ? products.slice(0, 5) : []);
    } catch (error) {
      console.error('Error loading low stock products:', error);
    }
  };

  const loadRecentSales = async () => {
    try {
      const response = await salesAPI.list({ limit: 5 });
      const sales = response.data.results || response.data || [];
      setRecentSales(Array.isArray(sales) ? sales : []);
    } catch (error) {
      console.error('Error loading recent sales:', error);
    }
  };

  const loadTopProducts = async (period) => {
    try {
      const today = new Date();
      let dateFrom = null;
      
      if (period === '1D') {
        dateFrom = new Date(today.setHours(0, 0, 0, 0)).toISOString();
      } else if (period === '1W') {
        dateFrom = new Date(today.setDate(today.getDate() - 7)).toISOString();
      } else if (period === '1M') {
        dateFrom = new Date(today.getFullYear(), today.getMonth(), 1).toISOString();
      } else if (period === '3M') {
        dateFrom = new Date(today.getFullYear(), today.getMonth() - 3, 1).toISOString();
      } else if (period === '6M') {
        dateFrom = new Date(today.getFullYear(), today.getMonth() - 6, 1).toISOString();
      } else if (period === '1Y') {
        dateFrom = new Date(today.getFullYear(), 0, 1).toISOString();
      }
      
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      
      const response = await reportsAPI.products(params);
      if (response.data && response.data.products) {
        setTopProducts(response.data.products.slice(0, 5));
      }
    } catch (error) {
      console.error('Error loading top products:', error);
    }
  };

  useEffect(() => {
    if (timeFilter) {
      loadTopProducts(timeFilter);
    }
  }, [timeFilter]);

  if (loading) {
    return (
      <Layout>
        <div className="dashboard-loading">Loading...</div>
      </Layout>
    );
  }

  const data = dashboardData || {
    today: { sales_count: 0, total: 0 },
    month: { total: 0 },
    low_stock_count: 0,
    total_sales: 0,
    total_purchase: 0,
    total_expenses: 0,
    profit: 0,
    sales_returns: { total: 0, count: 0 },
    purchase_returns: { total: 0 },
    invoice_due: 0,
    payment_returns: 0,
    growth: {
      sales: 0,
      returns: 0,
      purchase: 0,
      profit: 0,
      expenses: 0,
      payment_returns: 0,
    },
    overall: {
      suppliers: 0,
      customers: 0,
      orders: 0,
    },
  };

  const formatGrowth = (value) => {
    if (value === 0) return '0%';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  const getGrowthClass = (value) => {
    return value >= 0 ? 'positive' : 'negative';
  };

  return (
    <Layout>
      <div className="dashboard-page">
        <div className="dashboard-header">
          <div>
            <h1>Welcome, {user?.username || user?.first_name || 'Admin'}</h1>
            <p className="dashboard-subtitle">
              You have {data.today?.sales_count || 0}+ Orders, Today
            </p>
          </div>
          {lowStockProducts.length > 0 && (
            <div className="low-stock-alert">
              <span>⚠️</span>
              <span>
                Your Product {lowStockProducts[0]?.name} is running Low, already below {lowStockProducts[0]?.low_stock_threshold || 5} Pcs., Add Stock
              </span>
            </div>
          )}
        </div>

        {/* Statistics Cards */}
        <div className="stats-grid">
          <div className="stat-card sales">
            <div className="stat-header">
              <h3>Total Sales</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.sales || 0)}`}>
                {formatGrowth(data.growth?.sales || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.total_sales || data.month?.total || 0)}</div>
          </div>

          <div className="stat-card sales-return">
            <div className="stat-header">
              <h3>Total Sales Return</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.returns || 0)}`}>
                {formatGrowth(data.growth?.returns || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.sales_returns?.total || 0)}</div>
          </div>

          <div className="stat-card purchase">
            <div className="stat-header">
              <h3>Total Purchase</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.purchase || 0)}`}>
                {formatGrowth(data.growth?.purchase || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.total_purchase || 0)}</div>
          </div>

          <div className="stat-card purchase-return">
            <div className="stat-header">
              <h3>Total Purchase Return</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.purchase || 0)}`}>
                {formatGrowth(data.growth?.purchase || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.purchase_returns?.total || 0)}</div>
          </div>

          <div className="stat-card profit">
            <div className="stat-header">
              <h3>Profit</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.profit || 0)}`}>
                {formatGrowth(data.growth?.profit || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.profit || 0)}</div>
            <div className="stat-footer">vs Last Month</div>
          </div>

          <div className="stat-card invoice-due">
            <div className="stat-header">
              <h3>Invoice Due</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.sales || 0)}`}>
                {formatGrowth(data.growth?.sales || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.invoice_due || 0)}</div>
            <div className="stat-footer">vs Last Month</div>
          </div>

          <div className="stat-card expenses">
            <div className="stat-header">
              <h3>Total Expenses</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.expenses || 0)}`}>
                {formatGrowth(data.growth?.expenses || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.total_expenses || 0)}</div>
            <div className="stat-footer">vs Last Month</div>
          </div>

          <div className="stat-card payment-returns">
            <div className="stat-header">
              <h3>Total Payment Returns</h3>
              <span className={`stat-badge ${getGrowthClass(data.growth?.payment_returns || 0)}`}>
                {formatGrowth(data.growth?.payment_returns || 0)}
              </span>
            </div>
            <div className="stat-value">{formatCurrency(data.payment_returns || 0)}</div>
            <div className="stat-footer">vs Last Month</div>
          </div>
        </div>

        {/* Charts and Additional Info */}
        <div className="dashboard-grid">
          <div className="dashboard-card">
            <div className="card-header">
              <h3>Sales & Purchase</h3>
              <div className="time-filters">
                {['1D', '1W', '1M', '3M', '6M', '1Y'].map(period => (
                  <button
                    key={period}
                    className={`filter-btn ${timeFilter === period ? 'active' : ''}`}
                    onClick={() => setTimeFilter(period)}
                  >
                    {period}
                  </button>
                ))}
              </div>
            </div>
            <div className="chart-placeholder">
              <p>Chart visualization will be added here</p>
              <div className="chart-stats">
                <div>
                  <span className="chart-label">Total Purchase</span>
                  <span className="chart-value">{formatCurrency(data.total_purchase || 0)}</span>
                </div>
                <div>
                  <span className="chart-label">Total Sales</span>
                  <span className="chart-value">{formatCurrency(data.total_sales || data.month?.total || 0)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="dashboard-card">
            <div className="card-header">
              <h3>Overall Information</h3>
            </div>
            <div className="info-grid">
              <div className="info-item">
                <div className="info-label">Suppliers</div>
                <div className="info-value">{data.overall?.suppliers || 0}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Customer</div>
                <div className="info-value">{data.overall?.customers || 0}</div>
              </div>
              <div className="info-item">
                <div className="info-label">Orders</div>
                <div className="info-value">{data.today?.sales_count || data.overall?.orders || 0}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Top Selling Products */}
        {topProducts.length > 0 && (
          <div className="dashboard-card">
            <div className="card-header">
              <h3>Top Selling Products</h3>
              <div className="time-filters">
                <button className={`filter-btn ${timeFilter === '1D' ? 'active' : ''}`} onClick={() => setTimeFilter('1D')}>Today</button>
                <button className={`filter-btn ${timeFilter === '1W' ? 'active' : ''}`} onClick={() => setTimeFilter('1W')}>Weekly</button>
                <button className={`filter-btn ${timeFilter === '1M' ? 'active' : ''}`} onClick={() => setTimeFilter('1M')}>Monthly</button>
              </div>
            </div>
            <div className="products-list">
              {topProducts.map((product, idx) => (
                <div key={idx} className="product-item">
                  <div className="product-info-small">
                    <div className="product-name-small">{product.product__name || 'N/A'}</div>
                    <div className="product-id">SKU: {product.product__sku || 'N/A'}</div>
                  </div>
                  <div className="product-sales-info">
                    <div className="sales-stats">
                      <span className="sales-label">Sold:</span>
                      <span className="sales-value">{formatNumber(product.quantity_sold || 0)}</span>
                    </div>
                    <div className="sales-stats">
                      <span className="sales-label">Revenue:</span>
                      <span className="sales-value">{formatCurrency(product.revenue || 0)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Low Stock Products */}
        <div className="dashboard-card">
          <div className="card-header">
            <h3>Low Stock Products</h3>
            <Link to="/products?low_stock=true" className="view-all-link">View All</Link>
          </div>
          <div className="products-list">
            {lowStockProducts.length === 0 ? (
              <div className="empty-state">No low stock products</div>
            ) : (
              lowStockProducts.map(product => (
                <div key={product.id} className="product-item">
                  {product.image_url && (
                    <div className="product-image-small">
                      <img src={product.image_url} alt={product.name} />
                    </div>
                  )}
                  <div className="product-info-small">
                    <div className="product-name-small">{product.name}</div>
                    <div className="product-id">ID : #{product.sku}</div>
                  </div>
                  <div className="product-stock-info">
                    <span className="stock-label">Instock</span>
                    <span className="stock-value">{formatNumber(product.stock_quantity)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Sales */}
        <div className="dashboard-card">
          <div className="card-header">
            <h3>Recent Sales</h3>
            <Link to="/sales" className="view-all-link">View All</Link>
          </div>
          <div className="sales-list">
            {recentSales.length === 0 ? (
              <div className="empty-state">No recent sales</div>
            ) : (
              recentSales.map(sale => (
                <div key={sale.id} className="sale-item">
                  <div className="sale-info">
                    <div className="sale-name">{sale.sale_number || `Sale #${sale.id}`}</div>
                    <div className="sale-date">{new Date(sale.created_at).toLocaleDateString()}</div>
                  </div>
                  <div className="sale-amount">{formatCurrency(sale.total || 0)}</div>
                  <div className="sale-status">
                    <span className={`status-badge ${sale.status || 'completed'}`}>
                      {sale.status || 'Completed'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;
