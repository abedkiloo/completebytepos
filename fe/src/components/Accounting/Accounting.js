import React, { useState, useEffect, useCallback } from 'react';
import { accountingAPI, bankAccountsAPI } from '../../services/api';
import { formatCurrency, formatDate } from '../../utils/formatters';
import SearchableSelect from '../Shared/SearchableSelect';
import Layout from '../Layout/Layout';
import './Accounting.css';

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
    <Layout>
      <div className="accounting-page">
        <div className="page-header">
          <div>
            <h1>Accounting & Financial Reports</h1>
            <p>View comprehensive accounting reports and manage financial records</p>
          </div>
        </div>

        <div className="accounting-layout">
          {/* Left Sidebar - Report Selection */}
          <div className="accounting-sidebar">
            <div className="sidebar-header">
              <h3>Reports</h3>
            </div>
            <nav className="report-menu">
              <button
                className={`menu-item ${activeTab === 'balance-sheet' ? 'active' : ''}`}
                onClick={() => setActiveTab('balance-sheet')}
              >
                Balance Sheet
              </button>
              <button
                className={`menu-item ${activeTab === 'income-statement' ? 'active' : ''}`}
                onClick={() => setActiveTab('income-statement')}
              >
                Income Statement
              </button>
              <button
                className={`menu-item ${activeTab === 'trial-balance' ? 'active' : ''}`}
                onClick={() => setActiveTab('trial-balance')}
              >
                Trial Balance
              </button>
              <button
                className={`menu-item ${activeTab === 'cash-flow' ? 'active' : ''}`}
                onClick={() => setActiveTab('cash-flow')}
              >
                Cash Flow
              </button>
              <button
                className={`menu-item ${activeTab === 'account-statement' ? 'active' : ''}`}
                onClick={() => setActiveTab('account-statement')}
              >
                Account Statement
              </button>
              <button
                className={`menu-item ${activeTab === 'general-ledger' ? 'active' : ''}`}
                onClick={() => setActiveTab('general-ledger')}
              >
                General Ledger
              </button>
              <button
                className={`menu-item ${activeTab === 'accounts' ? 'active' : ''}`}
                onClick={() => setActiveTab('accounts')}
              >
                Chart of Accounts
              </button>
            </nav>
          </div>

          {/* Right Content Area */}
          <div className="accounting-content">
            {/* Date Filters */}
        {(activeTab === 'balance-sheet' || activeTab === 'trial-balance') && (
          <div className="report-filters">
            <div className="filter-group">
              <label>As of Date</label>
              <input
                type="date"
                name="date"
                value={filters.date}
                onChange={handleFilterChange}
              />
            </div>
          </div>
        )}

        {(activeTab === 'income-statement' || activeTab === 'cash-flow' || activeTab === 'general-ledger' || activeTab === 'account-statement') && (
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
            {activeTab === 'general-ledger' && (
              <div className="filter-group">
                <label>Account</label>
                <SearchableSelect
                  value={selectedAccount}
                  onChange={(e) => setSelectedAccount(e.target.value)}
                  options={accounts.map(account => ({
                    id: account.id,
                    name: `${account.account_code} - ${account.name}`
                  }))}
                  placeholder="Select Account"
                />
              </div>
            )}
            {activeTab === 'account-statement' && (
              <div className="filter-group">
                <label>Account</label>
                <SearchableSelect
                  value={selectedAccount}
                  onChange={(e) => setSelectedAccount(e.target.value)}
                  options={accounts.map(account => ({
                    id: account.id,
                    name: `${account.account_code} - ${account.name}`
                  }))}
                  placeholder="Select Account"
                />
              </div>
            )}
          </div>
        )}

        {/* Balance Sheet */}
        {activeTab === 'balance-sheet' && (
          <div className="report-content">
            {loading ? (
              <div className="loading-state">Loading balance sheet...</div>
            ) : balanceSheet ? (
              <>
                <div className="report-header">
                  <div>
                    <h2>Balance Sheet</h2>
                    <p>As of {formatDate(balanceSheet.date)}</p>
                  </div>
                  <button 
                    className="btn-download"
                    onClick={() => accountingAPI.reports.downloadBalanceSheet({ date: filters.date })}
                    title="Download PDF"
                  >📥 Download PDF
                  </button>
                </div>
                
                <div className="balance-sheet-grid">
                  <div className="balance-sheet-section">
                    <h3>Assets</h3>
                    <table className="account-table">
                      <tbody>
                        {Object.entries(balanceSheet.assets).map(([name, data]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td className="amount">{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className="total-row">
                          <td><strong>Total Assets</strong></td>
                          <td className="amount"><strong>{formatCurrency(balanceSheet.total_assets)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="balance-sheet-section">
                    <h3>Liabilities</h3>
                    <table className="account-table">
                      <tbody>
                        {Object.entries(balanceSheet.liabilities).map(([name, data]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td className="amount">{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className="total-row">
                          <td><strong>Total Liabilities</strong></td>
                          <td className="amount"><strong>{formatCurrency(balanceSheet.total_liabilities)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="balance-sheet-section">
                    <h3>Equity</h3>
                    <table className="account-table">
                      <tbody>
                        {Object.entries(balanceSheet.equity).map(([name, data]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td className="amount">{formatCurrency(data.balance)}</td>
                          </tr>
                        ))}
                        <tr className="total-row">
                          <td><strong>Total Equity</strong></td>
                          <td className="amount"><strong>{formatCurrency(balanceSheet.total_equity)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="balance-sheet-summary">
                  <div className="summary-item">
                    <span>Total Liabilities + Equity:</span>
                    <span className="amount">{formatCurrency(balanceSheet.total_liabilities + balanceSheet.total_equity)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">No balance sheet data available</div>
            )}
          </div>
        )}

        {/* Income Statement */}
        {activeTab === 'income-statement' && (
          <div className="report-content">
            {loading ? (
              <div className="loading-state">Loading income statement...</div>
            ) : incomeStatement ? (
              <>
                <div className="report-header">
                  <h2>Income Statement (Profit & Loss)</h2>
                  <p>Period: {formatDate(incomeStatement.period_start)} to {formatDate(incomeStatement.period_end)}</p>
                </div>
                
                <div className="income-statement-content">
                  <div className="statement-section">
                    <h3>Revenue</h3>
                    <table className="account-table">
                      <tbody>
                        {Object.entries(incomeStatement.revenue).map(([name, data]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td className="amount">{formatCurrency(data.amount)}</td>
                          </tr>
                        ))}
                        <tr className="total-row">
                          <td><strong>Total Revenue</strong></td>
                          <td className="amount"><strong>{formatCurrency(incomeStatement.total_revenue)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="statement-section">
                    <h3>Expenses</h3>
                    <table className="account-table">
                      <tbody>
                        {Object.entries(incomeStatement.expenses).map(([name, data]) => (
                          <tr key={name}>
                            <td>{name}</td>
                            <td className="amount">{formatCurrency(data.amount)}</td>
                          </tr>
                        ))}
                        <tr className="total-row">
                          <td><strong>Total Expenses</strong></td>
                          <td className="amount"><strong>{formatCurrency(incomeStatement.total_expenses)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="statement-summary">
                    <div className="summary-item net-income">
                      <span>Net Income (Profit/Loss):</span>
                      <span className={`amount ${incomeStatement.net_income >= 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(incomeStatement.net_income)}
                      </span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">No income statement data available</div>
            )}
          </div>
        )}

        {/* Trial Balance */}
        {activeTab === 'trial-balance' && (
          <div className="report-content">
            {loading ? (
              <div className="loading-state">Loading trial balance...</div>
            ) : trialBalance ? (
              <>
                <div className="report-header">
                  <div>
                    <h2>Trial Balance</h2>
                    <p>As of {formatDate(trialBalance.date)}</p>
                  </div>
                  <button 
                    className="btn-download"
                    onClick={() => accountingAPI.reports.downloadTrialBalance({ date: filters.date })}
                    title="Download PDF"
                  >
                    📥 Download PDF
                  </button>
                </div>
                
                <table className="trial-balance-table">
                  <thead>
                    <tr>
                      <th>Account Code</th>
                      <th>Account Name</th>
                      <th>Account Type</th>
                      <th>Debit</th>
                      <th>Credit</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trialBalance.accounts.map((account, idx) => (
                      <tr key={idx}>
                        <td>{account.account_code}</td>
                        <td>{account.account_name}</td>
                        <td className="capitalize">{account.account_type}</td>
                        <td className="amount">{account.debit > 0 ? formatCurrency(account.debit) : '-'}</td>
                        <td className="amount">{account.credit > 0 ? formatCurrency(account.credit) : '-'}</td>
                        <td className={`amount ${account.balance >= 0 ? 'positive' : 'negative'}`}>
                          {formatCurrency(account.balance)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="total-row">
                      <td colSpan="3"><strong>Total</strong></td>
                      <td className="amount"><strong>{formatCurrency(trialBalance.total_debits)}</strong></td>
                      <td className="amount"><strong>{formatCurrency(trialBalance.total_credits)}</strong></td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </>
            ) : (
              <div className="empty-state">No trial balance data available</div>
            )}
          </div>
        )}

        {/* Cash Flow */}
        {activeTab === 'cash-flow' && (
          <div className="report-content">
            {loading ? (
              <div className="loading-state">Loading cash flow statement...</div>
            ) : cashFlow ? (
              <>
                <div className="report-header">
                  <h2>Cash Flow Statement</h2>
                  <p>Period: {formatDate(cashFlow.period_start)} to {formatDate(cashFlow.period_end)}</p>
                </div>
                
                <div className="cash-flow-content">
                  <div className="cash-flow-section">
                    <h3>Operating Activities</h3>
                    <table className="account-table">
                      <tbody>
                        <tr>
                          <td>Cash from Sales</td>
                          <td className="amount positive">{formatCurrency(cashFlow.operating_activities.cash_from_sales)}</td>
                        </tr>
                        <tr>
                          <td>Cash Paid for Expenses</td>
                          <td className="amount negative">({formatCurrency(cashFlow.operating_activities.cash_paid_expenses)})</td>
                        </tr>
                        <tr className="total-row">
                          <td><strong>Net Cash from Operating Activities</strong></td>
                          <td className="amount"><strong>{formatCurrency(cashFlow.operating_activities.net_operating)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="cash-flow-section">
                    <h3>Investing Activities</h3>
                    <table className="account-table">
                      <tbody>
                        <tr className="total-row">
                          <td><strong>Net Cash from Investing Activities</strong></td>
                          <td className="amount"><strong>{formatCurrency(cashFlow.investing_activities.total)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <div className="cash-flow-section">
                    <h3>Financing Activities</h3>
                    <table className="account-table">
                      <tbody>
                        <tr className="total-row">
                          <td><strong>Net Cash from Financing Activities</strong></td>
                          <td className="amount"><strong>{formatCurrency(cashFlow.financing_activities.total)}</strong></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="cash-flow-summary">
                  <div className="summary-item">
                    <span>Net Increase (Decrease) in Cash:</span>
                    <span className={`amount ${cashFlow.net_cash_flow >= 0 ? 'positive' : 'negative'}`}>
                      {formatCurrency(cashFlow.net_cash_flow)}
                    </span>
                  </div>
                  <div className="summary-item">
                    <span>Beginning Cash:</span>
                    <span className="amount">{formatCurrency(cashFlow.beginning_cash)}</span>
                  </div>
                  <div className="summary-item net-cash">
                    <span>Ending Cash:</span>
                    <span className="amount">{formatCurrency(cashFlow.ending_cash)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">No cash flow data available</div>
            )}
          </div>
        )}

        {/* Account Statement */}
        {activeTab === 'account-statement' && (
          <div className="report-content">
            {!selectedAccount ? (
              <div className="empty-state">Please select an account to view statement</div>
            ) : loading ? (
              <div className="loading-state">Loading account statement...</div>
            ) : accountStatement ? (
              <>
                <div className="report-header">
                  <h2>Account Statement</h2>
                  <p>{accountStatement.account.account_code} - {accountStatement.account.account_name}</p>
                  <p>Account Type: {accountStatement.account.account_type}</p>
                  <p>Period: {formatDate(accountStatement.period_start)} to {formatDate(accountStatement.period_end)}</p>
                </div>
                
                <div className="ledger-info">
                  <div className="info-item">
                    <span>Opening Balance:</span>
                    <span className="amount">{formatCurrency(accountStatement.account.opening_balance)} {accountStatement.account.currency || 'KES'}</span>
                  </div>
                  <div className="info-item">
                    <span>Closing Balance:</span>
                    <span className="amount">{formatCurrency(accountStatement.closing_balance)} {accountStatement.account.currency || 'KES'}</span>
                  </div>
                </div>

                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Entry #</th>
                      <th>Type</th>
                      <th>Description</th>
                      <th>Reference</th>
                      <th>Amount</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accountStatement.entries.map((entry, idx) => (
                      <tr key={idx}>
                        <td>{formatDate(entry.entry_date)}</td>
                        <td>{entry.entry_number}</td>
                        <td className="capitalize">{entry.entry_type}</td>
                        <td>{entry.description}</td>
                        <td>{entry.reference || '-'}</td>
                        <td className={`amount ${entry.entry_type === 'debit' ? 'positive' : 'negative'}`}>
                          {entry.entry_type === 'debit' ? '+' : '-'}{formatCurrency(entry.amount)}
                        </td>
                        <td className="amount">{formatCurrency(entry.balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <div className="empty-state">No account statement data available</div>
            )}
          </div>
        )}

        {/* General Ledger */}
        {activeTab === 'general-ledger' && (
          <div className="report-content">
            {!selectedAccount ? (
              <div className="empty-state">Please select an account to view general ledger</div>
            ) : loading ? (
              <div className="loading-state">Loading general ledger...</div>
            ) : generalLedger ? (
              <>
                <div className="report-header">
                  <h2>General Ledger</h2>
                  <p>{generalLedger.account.account_code} - {generalLedger.account.name}</p>
                  <p>Period: {formatDate(filters.date_from)} to {formatDate(filters.date_to)}</p>
                </div>
                
                <div className="ledger-info">
                  <div className="info-item">
                    <span>Opening Balance:</span>
                    <span className="amount">{formatCurrency(generalLedger.account.opening_balance)}</span>
                  </div>
                  <div className="info-item">
                    <span>Closing Balance:</span>
                    <span className="amount">{formatCurrency(generalLedger.closing_balance)}</span>
                  </div>
                </div>

                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Entry #</th>
                      <th>Type</th>
                      <th>Description</th>
                      <th>Reference</th>
                      <th>Amount</th>
                      <th>Running Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {generalLedger.entries.map((entry, idx) => (
                      <tr key={idx}>
                        <td>{formatDate(entry.entry_date)}</td>
                        <td>{entry.entry_number}</td>
                        <td className="capitalize">{entry.entry_type}</td>
                        <td>{entry.description}</td>
                        <td>{entry.reference || '-'}</td>
                        <td className={`amount ${entry.entry_type === 'debit' ? 'debit' : 'credit'}`}>
                          {formatCurrency(entry.amount)}
                        </td>
                        <td className="amount">{formatCurrency(entry.running_balance)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : (
              <div className="empty-state">No general ledger data available</div>
            )}
          </div>
        )}

        {/* Chart of Accounts */}
        {activeTab === 'accounts' && (
          <div className="report-content">
            {loading ? (
              <div className="loading-state">Loading accounts...</div>
            ) : accounts.length > 0 ? (
              <table className="accounts-table">
                <thead>
                  <tr>
                    <th>Account Code</th>
                    <th>Account Name</th>
                    <th>Type</th>
                    <th>Current Balance</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map(account => (
                    <tr key={account.id}>
                      <td>{account.account_code}</td>
                      <td>{account.name}</td>
                      <td className="capitalize">{account.account_type_name}</td>
                      <td className={`amount ${account.current_balance >= 0 ? 'positive' : 'negative'}`}>
                        {formatCurrency(account.current_balance)}
                      </td>
                      <td>
                        <span className={`status-badge ${account.is_active ? 'active' : 'inactive'}`}>
                          {account.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">No accounts found</div>
            )}
          </div>
        )}
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Accounting;

