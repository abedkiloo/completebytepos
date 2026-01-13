import React from 'react';
import { useNavigate } from 'react-router-dom';
import './ReportsList.css';

const ReportsList = () => {
  const navigate = useNavigate();

  const reports = [
    {
      id: 'sales',
      name: 'Sales Report',
      icon: '📊',
      hasDetail: true,
      description: 'View sales performance and revenue analytics',
    },
    {
      id: 'purchase',
      name: 'Purchase report',
      icon: '🕐',
      hasDetail: false,
      description: 'Track purchase orders and supplier transactions',
    },
    {
      id: 'inventory',
      name: 'Inventory Report',
      icon: '🔽',
      hasDetail: true,
      description: 'Monitor stock levels and inventory movements',
    },
    {
      id: 'invoice',
      name: 'Invoice Report',
      icon: '💰',
      hasDetail: false,
      description: 'View invoice status and payment tracking',
    },
    {
      id: 'supplier',
      name: 'Supplier Report',
      icon: '⭐',
      hasDetail: true,
      description: 'Analyze supplier performance and transactions',
    },
    {
      id: 'customer',
      name: 'Customer Report',
      icon: '👤',
      hasDetail: true,
      description: 'Customer purchase history and analytics',
    },
    {
      id: 'products',
      name: 'Product Report',
      icon: '📋',
      hasDetail: true,
      description: 'Product sales performance and trends',
    },
    {
      id: 'expense',
      name: 'Expense Report',
      icon: '🔗',
      hasDetail: false,
      description: 'Track business expenses and spending',
    },
    {
      id: 'income',
      name: 'Income Report',
      icon: '📈',
      hasDetail: false,
      description: 'View income sources and revenue streams',
    },
    {
      id: 'tax',
      name: 'Tax Report',
      icon: '📉',
      hasDetail: false,
      description: 'Tax calculations and compliance reports',
    },
    {
      id: 'profit-loss',
      name: 'Profit & Loss',
      icon: '🔄',
      hasDetail: false,
      description: 'Profit and loss statement analysis',
    },
    {
      id: 'annual',
      name: 'Annual Report',
      icon: '🔍',
      hasDetail: false,
      description: 'Comprehensive annual business overview',
    },
  ];

  const handleReportClick = (reportId) => {
    navigate(`/reports?report=${reportId}`);
  };

  return (
    <div className="reports-list-page">
      <div className="reports-list-header">
        <h1>Reports</h1>
      </div>

      <div className="reports-list-container">
        {reports.map((report) => (
          <div
            key={report.id}
            className="report-item"
            onClick={() => handleReportClick(report.id)}
          >
            <div className="report-item-icon">{report.icon}</div>
            <div className="report-item-content">
              <div className="report-item-name">{report.name}</div>
              <div className="report-item-description">{report.description}</div>
            </div>
            {report.hasDetail && (
              <div className="report-item-arrow">›</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ReportsList;
