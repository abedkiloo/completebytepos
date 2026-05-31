import React, { useState, useEffect, useCallback } from 'react';
import { accountingAPI, bankAccountsAPI } from '../../services/api';
import { formatCurrency, formatDate } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import { PageShell, PageHeader, FilterBar, SearchField, FilterField } from '../page';
import { Input } from '../ui/input';
import { cn } from '../../lib/cn';
import {
  ReportPanel,
  ReportLoading,
  ReportEmpty,
  ReportDownloadButton,
  AccountStatusBadge,
  amt,
  R,
} from './accountingReportUI';

const Accounting = () => {
  const [activeTab, setActiveTab] = useState('balance-sheet');
  const [loading, setLoading] = useState(false);
  const [balanceSheet, setBalanceSheet] = useState(null);
  const [incomeStatement, setIncomeStatement] = useState(null);
  const [trialBalance, setTrialBalance] = useState(null);
  const [cashFlow, setCashFlow] = useState(null);
  const [accountStatement, setAccountStatement] = useState(null);
  const [generalLedger, setGeneralLedger] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState('');
  const [selectedBankAccount, setSelectedBankAccount] = useState('');
  const [filters, setFilters] = useState({
    date: new Date().toISOString().split('T')[0],
    date_from: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0],
    date_to: new Date().toISOString().split('T')[0],
  });

  useEffect(() => {
    if (activeTab === 'balance-sheet') {
      loadBalanceSheet();
    } else if (activeTab === 'income-statement') {
      loadIncomeStatement();
    } else if (activeTab === 'trial-balance') {
      loadTrialBalance();
    } else if (activeTab === 'cash-flow') {
      loadCashFlow();
    } else if (activeTab === 'account-statement') {
      loadAccounts();  // Use accounting accounts, not bank accounts
    } else if (activeTab === 'accounts') {
      loadAccounts();
    }
  }, [activeTab, filters]);

  const loadCashFlow = useCallback(async () => {
    setLoading(true);
    try {
      const response = await accountingAPI.reports.cashFlow({
        date_from: filters.date_from,
        date_to: filters.date_to,
      });
      setCashFlow(response.data);
    } catch (error) {
      console.error('Error loading cash flow:', error);
      setCashFlow(null);
    } finally {
      setLoading(false);
    }
  }, [filters.date_from, filters.date_to]);

  const loadBankAccounts = async () => {
    setLoading(true);
    try {
      const response = await bankAccountsAPI.accounts.list({ is_active: 'true' });
      const data = response.data.results || response.data || [];
      setBankAccounts(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error loading bank accounts:', error);
      setBankAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadAccountStatement = async (accountId) => {
    if (!accountId) return;
    
    setLoading(true);
    try {
      const response = await accountingAPI.reports.accountStatement({
        account_id: accountId,
        date_from: filters.date_from,
        date_to: filters.date_to,
      });
      setAccountStatement(response.data);
    } catch (error) {
      console.error('Error loading account statement:', error);
      setAccountStatement(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'account-statement' && selectedAccount) {
      loadAccountStatement(selectedAccount);
    }
  }, [activeTab, selectedAccount, filters.date_from, filters.date_to]);

  const loadBalanceSheet = useCallback(async () => {
    setLoading(true);
    try {
      const response = await accountingAPI.reports.balanceSheet({ date: filters.date });
      setBalanceSheet(response.data);
    } catch (error) {
      console.error('Error loading balance sheet:', error);
      setBalanceSheet(null);
    } finally {
      setLoading(false);
    }
  }, [filters.date]);

  const loadIncomeStatement = useCallback(async () => {
    setLoading(true);
    try {
      const response = await accountingAPI.reports.incomeStatement({
        date_from: filters.date_from,
        date_to: filters.date_to,
      });
      setIncomeStatement(response.data);
    } catch (error) {
      console.error('Error loading income statement:', error);
      setIncomeStatement(null);
    } finally {
      setLoading(false);
    }
  }, [filters.date_from, filters.date_to]);

  const loadTrialBalance = useCallback(async () => {
    setLoading(true);
    try {
      const response = await accountingAPI.reports.trialBalance({ date: filters.date });
      setTrialBalance(response.data);
    } catch (error) {
      console.error('Error loading trial balance:', error);
      setTrialBalance(null);
    } finally {
      setLoading(false);
    }
  }, [filters.date]);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await accountingAPI.accounts.list({ is_active: 'true' });
      const data = response.data.results || response.data || [];
      setAccounts(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error loading accounts:', error);
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadGeneralLedger = async (accountId) => {
    if (!accountId) return;
    
    setLoading(true);
    try {
      const response = await accountingAPI.reports.generalLedger({
        account_id: accountId,
        date_from: filters.date_from,
        date_to: filters.date_to,
      });
      setGeneralLedger(response.data);
    } catch (error) {
      console.error('Error loading general ledger:', error);
      setGeneralLedger(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'general-ledger' && selectedAccount) {
      loadGeneralLedger(selectedAccount);
    }
  }, [activeTab, selectedAccount, filters.date_from, filters.date_to]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  return (
    <PageShell>
        <PageHeader
          title="Accounting"
          description="Financial statements, ledger, and account activity."
        />

        <div className="flex flex-col gap-6 lg:flex-row">
          <nav className="flex shrink-0 flex-row flex-wrap gap-1 lg:w-52 lg:flex-col lg:border-r lg:pr-4">
              <button
                type="button"
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'balance-sheet'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('balance-sheet')}
              >
                Balance Sheet
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'income-statement'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('income-statement')}
              >
                Income Statement
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'trial-balance'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('trial-balance')}
              >
                Trial Balance
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'cash-flow'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('cash-flow')}
              >
                Cash Flow
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'account-statement'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('account-statement')}
              >
                Account Statement
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'general-ledger'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('general-ledger')}
              >
                General Ledger
              </button>
              <button
                className={cn(
                  'rounded-md px-3 py-2 text-left text-sm font-medium transition',
                  activeTab === 'accounts'
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted'
                )}
                onClick={() => setActiveTab('accounts')}
              >
                Chart of Accounts
              </button>
            </nav>

          <div className="min-w-0 flex-1 space-y-4">
            {(activeTab === 'balance-sheet' || activeTab === 'trial-balance') && (
              <FilterBar>
                <FilterField label="As of date">
                  <Input
                    type="date"
                    name="date"
                    value={filters.date}
                    onChange={handleFilterChange}
                  />
                </FilterField>
              </FilterBar>
            )}

        {(activeTab === 'income-statement' || activeTab === 'cash-flow' || activeTab === 'general-ledger' || activeTab === 'account-statement') && (
          <FilterBar>
            <FilterField label="From date">
              <Input
                type="date"
                name="date_from"
                value={filters.date_from}
                onChange={handleFilterChange}
              />
            </FilterField>
            <FilterField label="To date">
              <Input
                type="date"
                name="date_to"
                value={filters.date_to}
                onChange={handleFilterChange}
              />
            </FilterField>
            {activeTab === 'general-ledger' && (
              <FilterField label="Account">
                <SearchableSelect
                  value={selectedAccount}
                  onChange={(e) => setSelectedAccount(e.target.value)}
                  options={accounts.map(account => ({
                    id: account.id,
                    name: `${account.account_code} - ${account.name}`
                  }))}
                  placeholder="Select Account"
                />
              </FilterField>
            )}
            {activeTab === 'account-statement' && (
              <FilterField label="Account">
                <SearchableSelect
                  value={selectedAccount}
                  onChange={(e) => setSelectedAccount(e.target.value)}
                  options={accounts.map(account => ({
                    id: account.id,
                    name: `${account.account_code} - ${account.name}`
                  }))}
                  placeholder="Select Account"
                />
              </FilterField>
            )}
          </FilterBar>
        )}

        {/* Balance Sheet */}
        {activeTab === 'balance-sheet' && (
          <ReportPanel>
            {loading ? (
              <ReportLoading />
            ) : balanceSheet ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>Balance Sheet</h2>
                    <p className={R.meta}>As of {formatDate(balanceSheet.date)}</p>
                  </div>
                  <ReportDownloadButton
                    onClick={() => accountingAPI.reports.downloadBalanceSheet({ date: filters.date })}
                  />
                </div>

                <div className={R.grid3}>
                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Assets</h3>
                    <table className={R.table}>
                      <tbody>
                        {Object.entries(balanceSheet.assets).map(([name, data]) => (
                          <tr key={name}>
                            <td className={R.accountTd}>{name}</td>
                            <td className={cn(R.accountTd, R.amount)}>{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Total Assets</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(balanceSheet.total_assets)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Liabilities</h3>
                    <table className={R.table}>
                      <tbody>
                        {Object.entries(balanceSheet.liabilities).map(([name, data]) => (
                          <tr key={name}>
                            <td className={R.accountTd}>{name}</td>
                            <td className={cn(R.accountTd, R.amount)}>{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Total Liabilities</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(balanceSheet.total_liabilities)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Equity</h3>
                    <table className={R.table}>
                      <tbody>
                        {Object.entries(balanceSheet.equity).map(([name, data]) => (
                          <tr key={name}>
                            <td className={R.accountTd}>{name}</td>
                            <td className={cn(R.accountTd, R.amount)}>{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Total Equity</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(balanceSheet.total_equity)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className={R.summaryWrap}>
                  <div className={R.summaryItem}>
                    <span>Total Liabilities + Equity:</span>
                    <span className={R.amount}>{formatCurrency(balanceSheet.total_liabilities + balanceSheet.total_equity)}</span>
                  </div>
                </div>
              </>
            ) : (
              <ReportEmpty>No balance sheet data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* Income Statement */}
        {activeTab === 'income-statement' && (
          <ReportPanel>
            {loading ? (
              <ReportLoading />
            ) : incomeStatement ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>Income Statement (Profit & Loss)</h2>
                    <p className={R.meta}>
                      Period: {formatDate(incomeStatement.period_start)} to {formatDate(incomeStatement.period_end)}
                    </p>
                  </div>
                </div>

                <div className={R.grid2}>
                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Revenue</h3>
                    <table className={R.table}>
                      <tbody>
                        {Object.entries(incomeStatement.revenue).map(([name, data]) => (
                          <tr key={name}>
                            <td className={R.accountTd}>{name}</td>
                            <td className={cn(R.accountTd, R.amount)}>{formatCurrency(data.amount)}</td>
                          </tr>
                        ))}
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Total Revenue</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(incomeStatement.total_revenue)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Expenses</h3>
                    <table className={R.table}>
                      <tbody>
                        {Object.entries(incomeStatement.expenses).map(([name, data]) => (
                          <tr key={name}>
                            <td className={R.accountTd}>{name}</td>
                            <td className={cn(R.accountTd, R.amount)}>{formatCurrency(data.amount)}</td>
                          </tr>
                        ))}
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Total Expenses</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(incomeStatement.total_expenses)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className={R.summaryWrap}>
                  <div className={R.summaryHighlight}>
                    <span>Net Income (Profit/Loss):</span>
                    <span className={amt(incomeStatement.net_income >= 0, incomeStatement.net_income < 0)}>
                      {formatCurrency(incomeStatement.net_income)}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <ReportEmpty>No income statement data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* Trial Balance */}
        {activeTab === 'trial-balance' && (
          <ReportPanel>
            {loading ? (
              <ReportLoading />
            ) : trialBalance ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>Trial Balance</h2>
                    <p className={R.meta}>As of {formatDate(trialBalance.date)}</p>
                  </div>
                  <ReportDownloadButton
                    onClick={() => accountingAPI.reports.downloadTrialBalance({ date: filters.date })}
                  />
                </div>

                <div className={R.tableWrap}>
                  <table className={R.table}>
                    <thead>
                      <tr className={R.thead}>
                        <th className={R.th}>Account Code</th>
                        <th className={R.th}>Account Name</th>
                        <th className={R.th}>Account Type</th>
                        <th className={R.th}>Debit</th>
                        <th className={R.th}>Credit</th>
                        <th className={R.th}>Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trialBalance.accounts.map((account, idx) => (
                        <tr key={idx} className={R.tr}>
                          <td className={R.td}>{account.account_code}</td>
                          <td className={R.td}>{account.account_name}</td>
                          <td className={cn(R.td, R.capitalize)}>{account.account_type}</td>
                          <td className={cn(R.td, R.amount)}>{account.debit > 0 ? formatCurrency(account.debit) : '-'}</td>
                          <td className={cn(R.td, R.amount)}>{account.credit > 0 ? formatCurrency(account.credit) : '-'}</td>
                          <td className={cn(R.td, amt(account.balance >= 0, account.balance < 0))}>
                            {formatCurrency(account.balance)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className={R.totalRow}>
                        <td className={R.td} colSpan="3"><strong>Total</strong></td>
                        <td className={cn(R.td, R.amount)}><strong>{formatCurrency(trialBalance.total_debits)}</strong></td>
                        <td className={cn(R.td, R.amount)}><strong>{formatCurrency(trialBalance.total_credits)}</strong></td>
                        <td className={R.td} />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </>
            ) : (
              <ReportEmpty>No trial balance data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* Cash Flow */}
        {activeTab === 'cash-flow' && (
          <ReportPanel>
            {loading ? (
              <ReportLoading />
            ) : cashFlow ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>Cash Flow Statement</h2>
                    <p className={R.meta}>
                      Period: {formatDate(cashFlow.period_start)} to {formatDate(cashFlow.period_end)}
                    </p>
                  </div>
                </div>

                <div className={R.grid3}>
                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Operating Activities</h3>
                    <table className={R.table}>
                      <tbody>
                        <tr>
                          <td className={R.accountTd}>Cash from Sales</td>
                          <td className={cn(R.accountTd, amt(true, false))}>{formatCurrency(cashFlow.operating_activities.cash_from_sales)}</td>
                        </tr>
                        <tr>
                          <td className={R.accountTd}>Cash Paid for Expenses</td>
                          <td className={cn(R.accountTd, amt(false, true))}>({formatCurrency(cashFlow.operating_activities.cash_paid_expenses)})</td>
                        </tr>
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Net Cash from Operating Activities</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(cashFlow.operating_activities.net_operating)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Investing Activities</h3>
                    <table className={R.table}>
                      <tbody>
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Net Cash from Investing Activities</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(cashFlow.investing_activities.total)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className={R.section}>
                    <h3 className={R.sectionTitle}>Financing Activities</h3>
                    <table className={R.table}>
                      <tbody>
                        <tr className={R.totalRow}>
                          <td className={R.accountTd}><strong>Net Cash from Financing Activities</strong></td>
                          <td className={cn(R.accountTd, R.amount)}><strong>{formatCurrency(cashFlow.financing_activities.total)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className={R.summaryWrap}>
                  <div className={R.cashItem}>
                    <span>Net Increase (Decrease) in Cash:</span>
                    <span className={amt(cashFlow.net_cash_flow >= 0, cashFlow.net_cash_flow < 0)}>
                      {formatCurrency(cashFlow.net_cash_flow)}
                    </span>
                  </div>
                  <div className={R.cashItem}>
                    <span>Beginning Cash:</span>
                    <span className={R.amount}>{formatCurrency(cashFlow.beginning_cash)}</span>
                  </div>
                  <div className={R.cashTotal}>
                    <span>Ending Cash:</span>
                    <span className={R.amount}>{formatCurrency(cashFlow.ending_cash)}</span>
                  </div>
                </div>
              </>
            ) : (
              <ReportEmpty>No cash flow data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* Account Statement */}
        {activeTab === 'account-statement' && (
          <ReportPanel>
            {!selectedAccount ? (
              <ReportEmpty>Please select an account to view statement</ReportEmpty>
            ) : loading ? (
              <ReportLoading />
            ) : accountStatement ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>Account Statement</h2>
                    <p className={R.meta}>{accountStatement.account.account_code} - {accountStatement.account.account_name}</p>
                    <p className={R.meta}>Account Type: {accountStatement.account.account_type}</p>
                    <p className={R.meta}>
                      Period: {formatDate(accountStatement.period_start)} to {formatDate(accountStatement.period_end)}
                    </p>
                  </div>
                </div>

                <div className={R.ledgerInfo}>
                  <div className={R.infoItem}>
                    <span>Opening Balance:</span>
                    <span className={R.amount}>{formatCurrency(accountStatement.account.opening_balance)} {accountStatement.account.currency || 'KES'}</span>
                  </div>
                  <div className={R.infoItem}>
                    <span>Closing Balance:</span>
                    <span className={R.amount}>{formatCurrency(accountStatement.closing_balance)} {accountStatement.account.currency || 'KES'}</span>
                  </div>
                </div>

                <div className={R.tableWrap}>
                  <table className={R.table}>
                    <thead>
                      <tr className={R.thead}>
                        <th className={R.th}>Date</th>
                        <th className={R.th}>Entry #</th>
                        <th className={R.th}>Type</th>
                        <th className={R.th}>Description</th>
                        <th className={R.th}>Reference</th>
                        <th className={R.th}>Amount</th>
                        <th className={R.th}>Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {accountStatement.entries.map((entry, idx) => (
                        <tr key={idx} className={R.tr}>
                          <td className={R.td}>{formatDate(entry.entry_date)}</td>
                          <td className={R.td}>{entry.entry_number}</td>
                          <td className={cn(R.td, R.capitalize)}>{entry.entry_type}</td>
                          <td className={R.td}>{entry.description}</td>
                          <td className={R.td}>{entry.reference || '-'}</td>
                          <td className={cn(R.td, amt(entry.entry_type === 'debit', entry.entry_type !== 'debit'))}>
                            {entry.entry_type === 'debit' ? '+' : '-'}{formatCurrency(entry.amount)}
                          </td>
                          <td className={cn(R.td, R.amount)}>{formatCurrency(entry.balance)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <ReportEmpty>No account statement data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* General Ledger */}
        {activeTab === 'general-ledger' && (
          <ReportPanel>
            {!selectedAccount ? (
              <ReportEmpty>Please select an account to view general ledger</ReportEmpty>
            ) : loading ? (
              <ReportLoading />
            ) : generalLedger ? (
              <>
                <div className={R.header}>
                  <div className={R.headerText}>
                    <h2 className={R.title}>General Ledger</h2>
                    <p className={R.meta}>{generalLedger.account.account_code} - {generalLedger.account.name}</p>
                    <p className={R.meta}>
                      Period: {formatDate(filters.date_from)} to {formatDate(filters.date_to)}
                    </p>
                  </div>
                </div>

                <div className={R.ledgerInfo}>
                  <div className={R.infoItem}>
                    <span>Opening Balance:</span>
                    <span className={R.amount}>{formatCurrency(generalLedger.account.opening_balance)}</span>
                  </div>
                  <div className={R.infoItem}>
                    <span>Closing Balance:</span>
                    <span className={R.amount}>{formatCurrency(generalLedger.closing_balance)}</span>
                  </div>
                </div>

                <div className={R.tableWrap}>
                  <table className={R.table}>
                    <thead>
                      <tr className={R.thead}>
                        <th className={R.th}>Date</th>
                        <th className={R.th}>Entry #</th>
                        <th className={R.th}>Type</th>
                        <th className={R.th}>Description</th>
                        <th className={R.th}>Reference</th>
                        <th className={R.th}>Amount</th>
                        <th className={R.th}>Running Balance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {generalLedger.entries.map((entry, idx) => (
                        <tr key={idx} className={R.tr}>
                          <td className={R.td}>{formatDate(entry.entry_date)}</td>
                          <td className={R.td}>{entry.entry_number}</td>
                          <td className={cn(R.td, R.capitalize)}>{entry.entry_type}</td>
                          <td className={R.td}>{entry.description}</td>
                          <td className={R.td}>{entry.reference || '-'}</td>
                          <td className={cn(R.td, amt(false, false, entry.entry_type === 'debit', entry.entry_type === 'credit'))}>
                            {formatCurrency(entry.amount)}
                          </td>
                          <td className={cn(R.td, R.amount)}>{formatCurrency(entry.running_balance)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <ReportEmpty>No general ledger data available</ReportEmpty>
            )}
          </ReportPanel>
        )}

        {/* Chart of Accounts */}
        {activeTab === 'accounts' && (
          <ReportPanel>
            {loading ? (
              <ReportLoading />
            ) : accounts.length > 0 ? (
              <div className={R.tableWrap}>
                <table className={R.table}>
                  <thead>
                    <tr className={R.thead}>
                      <th className={R.th}>Account Code</th>
                      <th className={R.th}>Account Name</th>
                      <th className={R.th}>Type</th>
                      <th className={R.th}>Current Balance</th>
                      <th className={R.th}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((account) => (
                      <tr key={account.id} className={R.tr}>
                        <td className={R.td}>{account.account_code}</td>
                        <td className={R.td}>{account.name}</td>
                        <td className={cn(R.td, R.capitalize)}>{account.account_type_name}</td>
                        <td className={cn(R.td, amt(account.current_balance >= 0, account.current_balance < 0))}>
                          {formatCurrency(account.current_balance)}
                        </td>
                        <td className={R.td}>
                          <AccountStatusBadge active={account.is_active} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <ReportEmpty>No accounts found</ReportEmpty>
            )}
          </ReportPanel>
        )}
          </div>
        </div>
      </PageShell>
  );
};

export default Accounting;

