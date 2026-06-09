import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { reportsLegacyReportEnabled } from '../../utils/reportDisplay';
import { PageShell, PageHeader, EmptyState } from '../page';
import { cn } from '../../lib/cn';

const ALL_REPORTS = [
  {
    id: 'sales',
    name: 'Sales Report',
    icon: '📊',
    hasDetail: true,
    description: 'View sales performance and revenue analytics',
  },
  {
    id: 'sales-by-person',
    name: 'Sales by staff',
    icon: '👥',
    hasDetail: true,
    description: 'Month-end performance per sales person — download for commission proof',
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

const ReportsList = () => {
  const navigate = useNavigate();
  const { settings: reportSettings } = useModuleSettings('reports');

  const reports = ALL_REPORTS.filter((report) =>
    reportsLegacyReportEnabled(reportSettings, report.id)
  );

  const handleReportClick = (reportId) => {
    navigate(`/reports?report=${reportId}`);
  };

  return (
    <PageShell>
      <PageHeader
        title="Reports"
        description="Legacy report types enabled in module settings."
      />

      {reports.length === 0 ? (
        <EmptyState title="No reports enabled" description="Turn on report types in System Settings." />
      ) : (
        <div className="grid gap-2">
          {reports.map((report) => (
            <button
              key={report.id}
              type="button"
              onClick={() => handleReportClick(report.id)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg border bg-card p-4 text-left shadow-sm',
                'transition hover:border-primary/30 hover:bg-muted/30'
              )}
            >
              <span className="text-2xl" aria-hidden>
                {report.icon}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-foreground">{report.name}</span>
                <span className="block text-sm text-muted-foreground">{report.description}</span>
              </span>
              {report.hasDetail ? (
                <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
              ) : null}
            </button>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default ReportsList;
