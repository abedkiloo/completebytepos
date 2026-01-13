import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportsAPI } from '../../services/api';
import { formatCurrency, formatNumber, formatDateTime, formatCompactCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import ReportsList from './ReportsList';
import '../../styles/shared.css';
import './Reports.css';

const Reports = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const reportParam = searchParams.get('report');
  
  // All hooks must be called at the top level, before any conditional returns
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    year: new Date().getFullYear(),
  });

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.year) params.year = filters.year;

      let response;
      switch (reportParam) {
        case 'sales':
          response = await reportsAPI.sales(params);
          break;
        case 'purchase':
          response = await reportsAPI.purchase(params);
          break;
        case 'inventory':
          response = await reportsAPI.inventory();
          break;
        case 'invoice':
          response = await reportsAPI.invoice(params);
          break;
        case 'supplier':
          response = await reportsAPI.supplier(params);
          break;
        case 'customer':
          response = await reportsAPI.customer(params);
          break;
        case 'products':
          response = await reportsAPI.products(params);
          break;
        case 'expense':
          response = await reportsAPI.expense(params);
          break;
        case 'income':
          response = await reportsAPI.income(params);
          break;
        case 'tax':
          response = await reportsAPI.tax(params);
          break;
        case 'profit-loss':
          response = await reportsAPI.profitLoss(params);
          break;
        case 'annual':
          response = await reportsAPI.annual({ year: filters.year });
          break;
        default:
          return;
      }
      setReportData(response.data);
    } catch (error) {
      console.error(`Error loading ${reportParam} report:`, error);
      setReportData(null);
    } finally {
      setLoading(false);
    }
  }, [reportParam, filters]);

  useEffect(() => {
    // Only load report if reportParam exists
    if (reportParam) {
      loadReport();
    }
  }, [loadReport, reportParam]);

  // If no report param, show list (after all hooks are declared)
  if (!reportParam) {
    return (
      <Layout>
        <ReportsList />
      </Layout>
    );
  }

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const renderReport = () => {
    if (loading) {
      return <div className="loading-state">Loading report...</div>;
    }

    if (!reportData) {
      return <div className="empty-state">No data available</div>;
    }

    switch (reportParam) {
      case 'sales':
        return renderSalesReport();
      case 'purchase':
        return renderPurchaseReport();
      case 'inventory':
        return renderInventoryReport();
      case 'invoice':
        return renderInvoiceReport();
      case 'supplier':
        return renderSupplierReport();
      case 'customer':
        return renderCustomerReport();
      case 'products':
        return renderProductsReport();
      case 'expense':
        return renderExpenseReport();
      case 'income':
        return renderIncomeReport();
      case 'tax':
        return renderTaxReport();
      case 'profit-loss':
        return renderProfitLossReport();
      case 'annual':
        return renderAnnualReport();
      default:
        return <div className="empty-state">Report not found</div>;
    }
  };

  const renderSalesReport = () => {
    const { summary, by_payment_method, daily_breakdown } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Sales</h3>
            <p className="summary-value">{summary?.total_sales || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Revenue</h3>
            <p className="summary-value">{formatCompactCurrency(summary?.total_revenue || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Items Sold</h3>
            <p className="summary-value">{formatNumber(summary?.total_items || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Tax</h3>
            <p className="summary-value">{formatCompactCurrency(summary?.total_tax || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Discount</h3>
            <p className="summary-value">{formatCompactCurrency(summary?.total_discount || 0)}</p>
          </div>
        </div>

        {by_payment_method && by_payment_method.length > 0 && (
          <div className="report-section">
            <h3>Sales by Payment Method</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Payment Method</th>
                    <th>Count</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {by_payment_method.map((item, idx) => (
                    <tr key={idx}>
                      <td className="capitalize">{item.payment_method}</td>
                      <td>{item.count}</td>
                      <td>{formatCurrency(item.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {daily_breakdown && daily_breakdown.length > 0 && (
          <div className="report-section">
            <h3>Daily Sales Breakdown</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Sales Count</th>
                    <th>Total Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {daily_breakdown.map((item, idx) => (
                    <tr key={idx}>
                      <td>{new Date(item.day).toLocaleDateString()}</td>
                      <td>{item.count}</td>
                      <td>{formatCurrency(item.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderPurchaseReport = () => {
    const { summary, purchases } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Purchases</h3>
            <p className="summary-value">{summary?.total_purchases || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Amount</h3>
            <p className="summary-value">{formatCurrency(summary?.total_amount || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Items</h3>
            <p className="summary-value">{formatNumber(summary?.total_items || 0)}</p>
          </div>
        </div>

        {purchases && purchases.length > 0 && (
          <div className="report-section">
            <h3>Purchase Details</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Product</th>
                    <th>Quantity</th>
                    <th>Unit Cost</th>
                    <th>Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {purchases.map((purchase, idx) => (
                    <tr key={idx}>
                      <td>{formatDateTime(purchase.date)}</td>
                      <td>{purchase.product_name}</td>
                      <td>{formatNumber(purchase.quantity)}</td>
                      <td>{formatCurrency(purchase.unit_cost)}</td>
                      <td>{formatCurrency(purchase.total_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderInventoryReport = () => {
    const { low_stock_count, out_of_stock_count, total_inventory_value, total_products_value, recent_movements } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Low Stock Items</h3>
            <p className="summary-value">{low_stock_count || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Out of Stock Items</h3>
            <p className="summary-value">{out_of_stock_count || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Inventory Value</h3>
            <p className="summary-value">{formatCurrency(total_inventory_value || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Products Value</h3>
            <p className="summary-value">{formatCurrency(total_products_value || 0)}</p>
          </div>
        </div>

        {recent_movements && recent_movements.length > 0 && (
          <div className="report-section">
            <h3>Recent Stock Movements</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Product</th>
                    <th>Type</th>
                    <th>Quantity</th>
                    <th>Unit Cost</th>
                    <th>Total Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {recent_movements.map((movement) => (
                    <tr key={movement.id}>
                      <td>{formatDateTime(movement.created_at)}</td>
                      <td>{movement.product_name}</td>
                      <td className="capitalize">{movement.movement_type}</td>
                      <td>{formatNumber(movement.quantity)}</td>
                      <td>{formatCurrency(movement.unit_cost)}</td>
                      <td>{formatCurrency(movement.total_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderInvoiceReport = () => {
    const { summary, invoices } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Invoices</h3>
            <p className="summary-value">{summary?.total_invoices || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Amount</h3>
            <p className="summary-value">{formatCurrency(summary?.total_amount || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Paid</h3>
            <p className="summary-value">{formatCurrency(summary?.paid_amount || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Outstanding</h3>
            <p className="summary-value">{formatCurrency(summary?.outstanding_amount || 0)}</p>
          </div>
        </div>

        {invoices && invoices.length > 0 && (
          <div className="report-section">
            <h3>Invoice Details</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Invoice #</th>
                    <th>Customer</th>
                    <th>Date</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{invoice.invoice_number}</td>
                      <td>{invoice.customer_name}</td>
                      <td>{formatDateTime(invoice.issued_date)}</td>
                      <td>{formatCurrency(invoice.total)}</td>
                      <td className="capitalize">{invoice.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderSupplierReport = () => {
    const { summary, suppliers } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Suppliers</h3>
            <p className="summary-value">{summary?.total_suppliers || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Purchases</h3>
            <p className="summary-value">{formatCurrency(summary?.total_purchases || 0)}</p>
          </div>
        </div>

        {suppliers && suppliers.length > 0 && (
          <div className="report-section">
            <h3>Supplier Performance</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Supplier</th>
                    <th>Total Purchases</th>
                    <th>Order Count</th>
                    <th>Avg Order Value</th>
                  </tr>
                </thead>
                <tbody>
                  {suppliers.map((supplier, idx) => (
                    <tr key={idx}>
                      <td>{supplier.name}</td>
                      <td>{formatCurrency(supplier.total_purchases)}</td>
                      <td>{supplier.order_count}</td>
                      <td>{formatCurrency(supplier.avg_order_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderCustomerReport = () => {
    const { summary, customers } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Customers</h3>
            <p className="summary-value">{summary?.total_customers || 0}</p>
          </div>
          <div className="summary-card">
            <h3>Total Sales</h3>
            <p className="summary-value">{formatCurrency(summary?.total_sales || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Avg Order Value</h3>
            <p className="summary-value">{formatCurrency(summary?.avg_order_value || 0)}</p>
          </div>
        </div>

        {customers && customers.length > 0 && (
          <div className="report-section">
            <h3>Customer Performance</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Customer</th>
                    <th>Total Purchases</th>
                    <th>Order Count</th>
                    <th>Avg Order Value</th>
                    <th>Last Purchase</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map((customer) => (
                    <tr key={customer.id}>
                      <td>{customer.name}</td>
                      <td>{formatCurrency(customer.total_purchases)}</td>
                      <td>{customer.order_count}</td>
                      <td>{formatCurrency(customer.avg_order_value)}</td>
                      <td>{customer.last_purchase ? formatDateTime(customer.last_purchase) : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderProductsReport = () => {
    const { products } = reportData;
    return (
      <>
        {products && products.length > 0 ? (
          <div className="report-section">
            <h3>Product Sales Performance</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Product Name</th>
                    <th>SKU</th>
                    <th>Category</th>
                    <th>Quantity Sold</th>
                    <th>Revenue</th>
                    <th>Avg Price</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product, idx) => (
                    <tr key={idx}>
                      <td>{product.product__name}</td>
                      <td>{product.product__sku}</td>
                      <td>{product.product__category__name || 'N/A'}</td>
                      <td>{formatNumber(product.quantity_sold)}</td>
                      <td>{formatCurrency(product.revenue)}</td>
                      <td>{formatCurrency(product.avg_price || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="empty-state">No product sales data available</div>
        )}
      </>
    );
  };

  const renderExpenseReport = () => {
    const { summary, expenses } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Expenses</h3>
            <p className="summary-value">{formatCurrency(summary?.total_expenses || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Expense Count</h3>
            <p className="summary-value">{summary?.expense_count || 0}</p>
          </div>
          <div className="summary-card">
            <h3>By Category</h3>
            <p className="summary-value">{summary?.category_count || 0}</p>
          </div>
        </div>

        {expenses && expenses.length > 0 && (
          <div className="report-section">
            <h3>Expense Details</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.map((expense) => (
                    <tr key={expense.id}>
                      <td>{formatDateTime(expense.expense_date)}</td>
                      <td>{expense.category_name}</td>
                      <td>{expense.description}</td>
                      <td>{formatCurrency(expense.amount)}</td>
                      <td className="capitalize">{expense.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderIncomeReport = () => {
    const { summary, income } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Income</h3>
            <p className="summary-value">{formatCurrency(summary?.total_income || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Income Count</h3>
            <p className="summary-value">{summary?.income_count || 0}</p>
          </div>
        </div>

        {income && income.length > 0 && (
          <div className="report-section">
            <h3>Income Details</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {income.map((item) => (
                    <tr key={item.id}>
                      <td>{formatDateTime(item.income_date)}</td>
                      <td>{item.category_name}</td>
                      <td>{item.description}</td>
                      <td>{formatCurrency(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderTaxReport = () => {
    const { summary, tax_breakdown } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Tax Collected</h3>
            <p className="summary-value">{formatCurrency(summary?.total_tax || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Tax Rate</h3>
            <p className="summary-value">{summary?.tax_rate || 0}%</p>
          </div>
        </div>

        {tax_breakdown && tax_breakdown.length > 0 && (
          <div className="report-section">
            <h3>Tax Breakdown</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Transaction</th>
                    <th>Taxable Amount</th>
                    <th>Tax Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {tax_breakdown.map((item, idx) => (
                    <tr key={idx}>
                      <td>{formatDateTime(item.date)}</td>
                      <td>{item.transaction_type}</td>
                      <td>{formatCurrency(item.taxable_amount)}</td>
                      <td>{formatCurrency(item.tax_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderProfitLossReport = () => {
    const { summary, monthly_breakdown } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Revenue</h3>
            <p className="summary-value">{formatCurrency(summary?.total_revenue || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Expenses</h3>
            <p className="summary-value">{formatCurrency(summary?.total_expenses || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Net Profit</h3>
            <p className="summary-value" style={{ color: (summary?.net_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
              {formatCurrency(summary?.net_profit || 0)}
            </p>
          </div>
          <div className="summary-card">
            <h3>Profit Margin</h3>
            <p className="summary-value">{summary?.profit_margin || 0}%</p>
          </div>
        </div>

        {monthly_breakdown && monthly_breakdown.length > 0 && (
          <div className="report-section">
            <h3>Monthly Breakdown</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Revenue</th>
                    <th>Expenses</th>
                    <th>Profit</th>
                  </tr>
                </thead>
                <tbody>
                  {monthly_breakdown.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.month}</td>
                      <td>{formatCurrency(item.revenue)}</td>
                      <td>{formatCurrency(item.expenses)}</td>
                      <td style={{ color: item.profit >= 0 ? '#10b981' : '#ef4444' }}>
                        {formatCurrency(item.profit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderAnnualReport = () => {
    const { summary, monthly_data } = reportData;
    return (
      <>
        <div className="report-summary">
          <div className="summary-card">
            <h3>Total Sales</h3>
            <p className="summary-value">{formatCurrency(summary?.total_sales || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Total Expenses</h3>
            <p className="summary-value">{formatCurrency(summary?.total_expenses || 0)}</p>
          </div>
          <div className="summary-card">
            <h3>Net Profit</h3>
            <p className="summary-value" style={{ color: (summary?.net_profit || 0) >= 0 ? '#10b981' : '#ef4444' }}>
              {formatCurrency(summary?.net_profit || 0)}
            </p>
          </div>
          <div className="summary-card">
            <h3>Growth Rate</h3>
            <p className="summary-value">{summary?.growth_rate || 0}%</p>
          </div>
        </div>

        {monthly_data && monthly_data.length > 0 && (
          <div className="report-section">
            <h3>Monthly Performance</h3>
            <div className="responsive-table-container">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Sales</th>
                    <th>Expenses</th>
                    <th>Profit</th>
                  </tr>
                </thead>
                <tbody>
                  {monthly_data.map((item, idx) => (
                    <tr key={idx}>
                      <td>{item.month}</td>
                      <td>{formatCurrency(item.sales)}</td>
                      <td>{formatCurrency(item.expenses)}</td>
                      <td style={{ color: item.profit >= 0 ? '#10b981' : '#ef4444' }}>
                        {formatCurrency(item.profit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </>
    );
  };

  const getReportTitle = () => {
    const titles = {
      'sales': 'Sales Report',
      'purchase': 'Purchase Report',
      'inventory': 'Inventory Report',
      'invoice': 'Invoice Report',
      'supplier': 'Supplier Report',
      'customer': 'Customer Report',
      'products': 'Product Report',
      'expense': 'Expense Report',
      'income': 'Income Report',
      'tax': 'Tax Report',
      'profit-loss': 'Profit & Loss',
      'annual': 'Annual Report',
    };
    return titles[reportParam] || 'Report';
  };

  const needsDateFilter = ['sales', 'purchase', 'invoice', 'customer', 'products', 'expense', 'income', 'tax', 'profit-loss'].includes(reportParam);
  const needsYearFilter = reportParam === 'annual';

  return (
    <Layout>
      <div className="reports-page">
        <div className="page-header">
          <div>
            <button 
              className="btn-back"
              onClick={() => navigate('/reports')}
            >
              ← Back to Reports
            </button>
            <h1>{getReportTitle()}</h1>
            <p>Comprehensive {getReportTitle().toLowerCase()} analytics</p>
          </div>
        </div>

        <div className="reports-main-content">
          {/* Date Filters */}
          {needsDateFilter && (
            <div className="report-filters">
              <div className="filter-group">
                <label>From Date</label>
                <input
                  type="date"
                  name="date_from"
                  value={filters.date_from}
                  onChange={handleFilterChange}
                />
              </div>
              <div className="filter-group">
                <label>To Date</label>
                <input
                  type="date"
                  name="date_to"
                  value={filters.date_to}
                  onChange={handleFilterChange}
                />
              </div>
            </div>
          )}

          {needsYearFilter && (
            <div className="report-filters">
              <div className="filter-group">
                <label>Year</label>
                <input
                  type="number"
                  name="year"
                  value={filters.year}
                  onChange={handleFilterChange}
                  min="2020"
                  max={new Date().getFullYear() + 1}
                />
              </div>
            </div>
          )}

          <div className="report-content">
            {renderReport()}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Reports;
