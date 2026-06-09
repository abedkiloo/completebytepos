import axios from 'axios';
import { resolveApiBaseUrl } from '../config/apiBaseUrl';
import {
  buildPdfFilename,
  downloadAuthenticatedPdf,
} from '../utils/pdfDownload';
import {
  isSessionTeardownActive,
  logoutAndRedirect,
} from '../utils/authSession';
import { markSessionActivity } from '../utils/sessionIdle';

const API_BASE_URL = resolveApiBaseUrl();

// Only add ngrok header if using ngrok URL
const isNgrokUrl = API_BASE_URL.includes('ngrok');
const defaultHeaders = {
  'Content-Type': 'application/json',
};
if (isNgrokUrl) {
  defaultHeaders['ngrok-skip-browser-warning'] = 'true';
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: defaultHeaders,
});

// Get token from localStorage
const getToken = () => {
  if (isSessionTeardownActive()) return null;
  return localStorage.getItem('access_token');
};

function isAuthBypassUrl(url = '') {
  return (
    url.includes('/token/refresh/') ||
    url.includes('/accounts/auth/logout/') ||
    url.includes('/accounts/auth/login/') ||
    url.includes('/auth/login')
  );
}

/** Single in-flight refresh so parallel 401s do not stampede the server. */
let refreshPromise = null;

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token');
    }

    const refreshHeaders = { 'Content-Type': 'application/json' };
    if (isNgrokUrl) {
      refreshHeaders['ngrok-skip-browser-warning'] = 'true';
    }

    const response = await axios.post(
      `${API_BASE_URL}/token/refresh/`,
      { refresh: refreshToken },
      { headers: refreshHeaders, timeout: 8000 }
    );

    const { access } = response.data || {};
    if (!access) {
      throw new Error('Refresh response missing access token');
    }

    localStorage.setItem('access_token', access);
    return access;
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

// Request interceptor - Add JWT token and branch ID to requests
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Only add branch header if branch support is enabled AND endpoint needs it
    // Default: DON'T send the header unless explicitly needed
    
    // First, check if this endpoint should NEVER get the branch header
    const neverSendBranchHeader = config.url && (
      config.url.includes('/auth/') ||
      config.url.includes('/settings/modules') ||
      config.url.includes('/settings/module-features') ||
      config.url.includes('/settings/branches') ||
      config.url.includes('/settings/tenants') ||
      config.url.includes('/settings/setup-status') ||
      config.url.includes('/settings/fresh-install') ||
      config.url.includes('/settings/store-settings') ||
      config.url.includes('/token/')
    );
    
    // If endpoint is in the never-send list, explicitly don't add header
    if (neverSendBranchHeader) {
      // Explicitly remove header if it exists
      delete config.headers['X-Branch-ID'];
      delete config.headers['x-branch-id'];
      return config;
    }
    
    // For other endpoints, check if branch support is enabled
    try {
      const enabledModules = JSON.parse(localStorage.getItem('enabled_modules') || '{}');
      const settingsModule = enabledModules['settings'];
      const multiBranchFeature = settingsModule?.features?.multi_branch_support;
      const branchSupportEnabled = multiBranchFeature?.is_enabled === true; // Explicitly check for true
      
      // Only add branch header if branch support is explicitly enabled
      if (branchSupportEnabled) {
        const currentBranch = localStorage.getItem('current_branch');
        if (currentBranch) {
          try {
            const branch = JSON.parse(currentBranch);
            if (branch && branch.id) {
              config.headers['X-Branch-ID'] = branch.id;
            }
          } catch (e) {
            // Ignore parsing errors
          }
        }
      } else {
        // Branch support disabled - explicitly remove header
        delete config.headers['X-Branch-ID'];
        delete config.headers['x-branch-id'];
      }
    } catch (e) {
      // If we can't check, default to NOT sending the header
      delete config.headers['X-Branch-ID'];
      delete config.headers['x-branch-id'];
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle token refresh on 401
api.interceptors.response.use(
  (response) => {
    if (getToken()) {
      markSessionActivity();
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config || {};
    const url = originalRequest.url || '';
    const status = error.response?.status;

    if (status !== 401) {
      return Promise.reject(error);
    }

    // Never recurse on auth endpoints or while tearing down the session.
    if (isAuthBypassUrl(url) || isSessionTeardownActive()) {
      return Promise.reject(error);
    }

    const isLoginRequest =
      url.includes('/accounts/auth/login') || url.includes('/auth/login');
    if (isLoginRequest) {
      return Promise.reject(error);
    }

    if (!originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const access = await refreshAccessToken();
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return api(originalRequest);
      } catch {
        await logoutAndRedirect({ reason: 'auth' });
        return Promise.reject(error);
      }
    }

    await logoutAndRedirect({ reason: 'auth' });
    return Promise.reject(error);
  }
);

// API endpoints
export const productsAPI = {
  list: (params) => api.get('/products/', { params }),
  get: (id) => api.get(`/products/${id}/`),
  create: (data) => api.post('/products/', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  update: (id, data) => api.put(`/products/${id}/`, data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  delete: (id, data) => api.delete(`/products/${id}/`, { data: data || {} }),
  search: (query, limit = 20) => api.get('/products/search/', { params: { q: query, limit } }),
  lowStock: () => api.get('/products/low_stock/'),
  outOfStock: () => api.get('/products/out_of_stock/'),
  bulkUpdate: (data) => api.post('/products/bulk_update/', data),
  bulkDelete: (data) => api.post('/products/bulk_delete/', data),
  bulkActivate: (data) => api.post('/products/bulk_activate/', data),
  bulkDeactivate: (data) => api.post('/products/bulk_deactivate/', data),
  statistics: () => api.get('/products/statistics/'),
  export: () => api.get('/products/export/', { responseType: 'blob' }),
  importCSV: (formData) => api.post('/products/import_csv/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  units: {
    list: (params) => api.get('/products/units/', { params }),
    options: () => api.get('/products/units/', { params: { format: 'options', is_active: 'true' } }),
    create: (data) => api.post('/products/units/', data),
  },
};

export const categoriesAPI = {
  list: (params) => api.get('/products/categories/', { params }),
  get: (id) => api.get(`/products/categories/${id}/`),
  create: (data) => api.post('/products/categories/', data),
  update: (id, data) => api.put(`/products/categories/${id}/`, data),
  delete: (id, data) => api.delete(`/products/categories/${id}/`, { data: data || {} }),
  products: (id) => api.get(`/products/categories/${id}/products/`),
};

export const sizesAPI = {
  list: (params) => api.get('/products/sizes/', { params }),
  get: (id) => api.get(`/products/sizes/${id}/`),
  create: (data) => api.post('/products/sizes/', data),
  update: (id, data) => api.put(`/products/sizes/${id}/`, data),
  delete: (id) => api.delete(`/products/sizes/${id}/`),
};

export const colorsAPI = {
  list: (params) => api.get('/products/colors/', { params }),
  get: (id) => api.get(`/products/colors/${id}/`),
  create: (data) => api.post('/products/colors/', data),
  update: (id, data) => api.put(`/products/colors/${id}/`, data),
  delete: (id) => api.delete(`/products/colors/${id}/`),
};

export const suppliersAPI = {
  list: (params) => api.get('/suppliers/suppliers/', { params }),
  get: (id) => api.get(`/suppliers/suppliers/${id}/`),
  create: (data) => api.post('/suppliers/suppliers/', data),
  update: (id, data) => api.put(`/suppliers/suppliers/${id}/`, data),
  delete: (id) => api.delete(`/suppliers/suppliers/${id}/`),
  statistics: () => api.get('/suppliers/suppliers/statistics/'),
  products: (id) => api.get(`/suppliers/suppliers/${id}/products/`),
};

export const dailyNotesAPI = {
  list: (params) => api.get('/daily-notes/notes/', { params }),
  get: (id) => api.get(`/daily-notes/notes/${id}/`),
  create: (data) => api.post('/daily-notes/notes/', data),
  update: (id, data) => api.put(`/daily-notes/notes/${id}/`, data),
  delete: (id) => api.delete(`/daily-notes/notes/${id}/`),
  recentDates: () => api.get('/daily-notes/notes/recent-dates/'),
};

export const dailyTasksAPI = {
  list: (params) => api.get('/daily-notes/tasks/', { params }),
  get: (id) => api.get(`/daily-notes/tasks/${id}/`),
  create: (data) => api.post('/daily-notes/tasks/', data),
  update: (id, data) => api.patch(`/daily-notes/tasks/${id}/`, data),
  delete: (id) => api.delete(`/daily-notes/tasks/${id}/`),
  toggleDone: (id) => api.post(`/daily-notes/tasks/${id}/toggle-done/`),
};

export const employeesAPI = {
  list: (params) => api.get('/employees/employees/', { params }),
  get: (id) => api.get(`/employees/employees/${id}/`),
  create: (data) => api.post('/employees/employees/', data),
  update: (id, data) => api.put(`/employees/employees/${id}/`, data),
  delete: (id) => api.delete(`/employees/employees/${id}/`),
  statistics: () => api.get('/employees/employees/statistics/'),
};

export const variantsAPI = {
  list: (params) => api.get('/products/variants/', { params }),
  get: (id) => api.get(`/products/variants/${id}/`),
  create: (data) => api.post('/products/variants/', data),
  update: (id, data) => api.put(`/products/variants/${id}/`, data),
  delete: (id, data) => api.delete(`/products/variants/${id}/`, { data: data || {} }),
  getByProduct: (productId) => api.get(`/products/variants/?product=${productId}`),
};

export const salesAPI = {
  list: (params) => api.get('/sales/', { params }),
  /** Today/month totals for dashboard (sales.view — no reports.view required). */
  dashboardSummary: () => api.get('/sales/dashboard-summary/'),
  get: (id) => api.get(`/sales/${id}/`),
  create: (data) => api.post('/sales/', data),
  receipt: (id) => api.get(`/sales/${id}/receipt/`),
  /** Register draft invoice (holding) — synced as items are added */
  activeHolding: () => api.get('/sales/active-holding/'),
  saveHolding: (data) => api.post('/sales/holding/', data),
  checkout: (id, data) => api.post(`/sales/${id}/checkout/`, data),
  cancelHolding: (id) => api.post(`/sales/${id}/cancel-holding/`),
  refund: (id, data) => api.post(`/sales/${id}/refund/`, data),
};

export const customersAPI = {
  list: (params) => api.get('/sales/customers/', { params }),
  get: (id) => api.get(`/sales/customers/${id}/`),
  create: (data) => api.post('/sales/customers/', data),
  update: (id, data) => api.put(`/sales/customers/${id}/`, data),
  delete: (id) => api.delete(`/sales/customers/${id}/`),
};

export const invoicesAPI = {
  list: (params) => api.get('/sales/invoices/', { params }),
  get: (id) => api.get(`/sales/invoices/${id}/`),
  create: (data) => api.post('/sales/invoices/', data),
  update: (id, data) => api.put(`/sales/invoices/${id}/`, data),
  delete: (id) => api.delete(`/sales/invoices/${id}/`),
  send: (id) => api.post(`/sales/invoices/${id}/send/`),
  statistics: (id) => api.get(`/sales/invoices/${id}/statistics/`),
  downloadPDF: (id, invoiceNumber) =>
    downloadAuthenticatedPdf(
      api,
      `/sales/invoices/${id}/download_pdf/`,
      buildPdfFilename('Invoice', invoiceNumber || id),
    ),
};

export const paymentsAPI = {
  list: (params) => api.get('/sales/payments/', { params }),
  get: (id) => api.get(`/sales/payments/${id}/`),
  create: (data) => api.post('/sales/payments/', data),
  update: (id, data) => api.put(`/sales/payments/${id}/`, data),
  delete: (id) => api.delete(`/sales/payments/${id}/`),
};

export const inventoryAPI = {
  list: (params) => api.get('/inventory/', { params }),
  get: (id) => api.get(`/inventory/${id}/`),
  adjust: (data) => api.post('/inventory/adjust/', data),
  purchase: (data) => api.post('/inventory/purchase/', data),
  transfer: (data) => api.post('/inventory/transfer/', data),
  undo: (id) => api.post(`/inventory/${id}/undo/`),
  bulkAdjust: (data) => api.post('/inventory/bulk_adjust/', data),
  lowStock: () => api.get('/inventory/low_stock/'),
  outOfStock: () => api.get('/inventory/out_of_stock/'),
  needsReorder: () => api.get('/inventory/needs_reorder/'),
  report: () => api.get('/inventory/report/'),
  movementsByType: (params) => api.get('/inventory/movements_by_type/', { params }),
  productHistory: (productId) => api.get('/inventory/product_history/', { params: { product_id: productId } }),
};

export const authAPI = {
  login: (credentials) => api.post('/accounts/auth/login/', credentials),
  logout: (refreshToken) => api.post('/accounts/auth/logout/', { refresh: refreshToken }),
  me: () => api.get('/accounts/auth/me/'),
  refreshToken: (refreshToken) => api.post('/token/refresh/', { refresh: refreshToken }),
};

export const reportsAPI = {
  dashboard: () => api.get('/reports/dashboard/'),
  sales: (params) => api.get('/reports/sales/', { params }),
  purchase: (params) => api.get('/reports/purchase/', { params }),
  products: (params) => api.get('/reports/products/', { params }),
  inventory: () => api.get('/reports/inventory/'),
  invoice: (params) => api.get('/reports/invoice/', { params }),
  supplier: (params) => api.get('/reports/supplier/', { params }),
  customer: (params) => api.get('/reports/customer/', { params }),
  expense: (params) => api.get('/reports/expense/', { params }),
  income: (params) => api.get('/reports/income/', { params }),
  tax: (params) => api.get('/reports/tax/', { params }),
  profitLoss: (params) => api.get('/reports/profit_loss/', { params }),
  annual: (params) => api.get('/reports/annual/', { params }),
  // New operational tiles for the redesigned Reports hub. Each accepts a
  // ?period=today|week|month query param.
  salesOverview: (params) => api.get('/reports/sales_overview/', { params }),
  topProducts: (params) => api.get('/reports/top_products/', { params }),
  cashAndPayments: (params) => api.get('/reports/cash_and_payments/', { params }),
  inventoryHealth: (params) => api.get('/reports/inventory_health/', { params }),
  customerOutstanding: (params) => api.get('/reports/customer_outstanding/', { params }),
  salesByPerson: (params) => api.get('/reports/sales_by_person/', { params }),
  salesByPersonCsv: (params) =>
    api.get('/reports/sales_by_person/', {
      params: { ...params, format: 'csv' },
      responseType: 'blob',
    }),
};

// Audit log — super-admin only on the backend (IsSuperAdmin).
export const auditLogAPI = {
  list: (params) => api.get('/accounts/audit-logs/', { params }),
  get: (id) => api.get(`/accounts/audit-logs/${id}/`),
};

export const pendingChangesAPI = {
  list: (params) => api.get('/approvals/pending-changes/', { params }),
  pending: () => api.get('/approvals/pending-changes/pending/'),
  get: (id) => api.get(`/approvals/pending-changes/${id}/`),
  approve: (id, data = {}) => api.post(`/approvals/pending-changes/${id}/approve/`, data),
  reject: (id, data) => api.post(`/approvals/pending-changes/${id}/reject/`, data),
};

export const barcodesAPI = {
  generate: (params) => api.get('/barcodes/generate', { params }),
  image: (params) => {
    console.log('[BarcodesAPI] image() called with params:', params);
    return api.get('/barcodes/image', { params, responseType: 'blob' });
  },
  generateMissing: (data) => api.post('/barcodes/generate_missing/', data),
  printLabels: (data, config = {}) => api.post('/barcodes/print_labels/', data, config),
};

export const expensesAPI = {
  list: (params) => api.get('/expenses/', { params }),
  get: (id) => api.get(`/expenses/${id}/`),
  create: (data) => api.post('/expenses/', data),
  update: (id, data) => api.put(`/expenses/${id}/`, data),
  delete: (id) => api.delete(`/expenses/${id}/`),
  approve: (id) => api.post(`/expenses/${id}/approve/`),
  statistics: () => api.get('/expenses/statistics/'),
  categories: {
    list: (params) => api.get('/expenses/categories/', { params }),
    get: (id) => api.get(`/expenses/categories/${id}/`),
    create: (data) => api.post('/expenses/categories/', data),
    update: (id, data) => api.put(`/expenses/categories/${id}/`, data),
    delete: (id) => api.delete(`/expenses/categories/${id}/`),
  },
};

export const accountingAPI = {
  accounts: {
    list: (params) => api.get('/accounting/accounts/', { params }),
    get: (id) => api.get(`/accounting/accounts/${id}/`),
    create: (data) => api.post('/accounting/accounts/', data),
    update: (id, data) => api.put(`/accounting/accounts/${id}/`, data),
    delete: (id) => api.delete(`/accounting/accounts/${id}/`),
    updateBalance: (id) => api.post(`/accounting/accounts/${id}/update_balance/`),
  },
  accountTypes: {
    list: () => api.get('/accounting/account-types/'),
    get: (id) => api.get(`/accounting/account-types/${id}/`),
  },
  journalEntries: {
    list: (params) => api.get('/accounting/journal-entries/', { params }),
    get: (id) => api.get(`/accounting/journal-entries/${id}/`),
    create: (data) => api.post('/accounting/journal-entries/', data),
  },
  transactions: {
    list: (params) => api.get('/accounting/transactions/', { params }),
    get: (id) => api.get(`/accounting/transactions/${id}/`),
    create: (data) => api.post('/accounting/transactions/', data),
  },
  reports: {
    balanceSheet: (params) => api.get('/accounting/reports/balance_sheet/', { params }),
    incomeStatement: (params) => api.get('/accounting/reports/income_statement/', { params }),
    trialBalance: (params) => api.get('/accounting/reports/trial_balance/', { params }),
    generalLedger: (params) => api.get('/accounting/reports/general_ledger/', { params }),
    cashFlow: (params) => api.get('/accounting/reports/cash_flow/', { params }),
    accountStatement: (params) => api.get('/accounting/reports/account_statement/', { params }),
    downloadBalanceSheet: (params) => {
      const queryString = new URLSearchParams({ ...params, format: 'pdf' }).toString();
      const date = params.date || new Date().toISOString().split('T')[0];
      return downloadAuthenticatedPdf(
        api,
        `/accounting/reports/balance_sheet/?${queryString}`,
        buildPdfFilename('BalanceSheet', date),
      );
    },
    downloadIncomeStatement: (params) => {
      const queryString = new URLSearchParams({ ...params, format: 'pdf' }).toString();
      const dateFrom = params.date_from || new Date().toISOString().split('T')[0];
      const dateTo = params.date_to || new Date().toISOString().split('T')[0];
      return downloadAuthenticatedPdf(
        api,
        `/accounting/reports/income_statement/?${queryString}`,
        buildPdfFilename('IncomeStatement', `${dateFrom}_to_${dateTo}`),
      );
    },
    downloadTrialBalance: (params) => {
      const queryString = new URLSearchParams({ ...params, format: 'pdf' }).toString();
      const date = params.date || new Date().toISOString().split('T')[0];
      return downloadAuthenticatedPdf(
        api,
        `/accounting/reports/trial_balance/?${queryString}`,
        buildPdfFilename('TrialBalance', date),
      );
    },
  },
};

export const incomeAPI = {
  list: (params) => api.get('/income/', { params }),
  get: (id) => api.get(`/income/${id}/`),
  create: (data) => api.post('/income/', data),
  update: (id, data) => api.put(`/income/${id}/`, data),
  delete: (id) => api.delete(`/income/${id}/`),
  approve: (id) => api.post(`/income/${id}/approve/`),
  statistics: () => api.get('/income/statistics/'),
  categories: {
    list: (params) => api.get('/income/categories/', { params }),
    get: (id) => api.get(`/income/categories/${id}/`),
    create: (data) => api.post('/income/categories/', data),
    update: (id, data) => api.put(`/income/categories/${id}/`, data),
    delete: (id) => api.delete(`/income/categories/${id}/`),
  },
};

export const bankAccountsAPI = {
  accounts: {
    list: (params) => api.get('/bank-accounts/accounts/', { params }),
    get: (id) => api.get(`/bank-accounts/accounts/${id}/`),
    create: (data) => api.post('/bank-accounts/accounts/', data),
    update: (id, data) => api.put(`/bank-accounts/accounts/${id}/`, data),
    delete: (id) => api.delete(`/bank-accounts/accounts/${id}/`),
    updateBalance: (id) => api.post(`/bank-accounts/accounts/${id}/update_balance/`),
  },
  transactions: {
    list: (params) => api.get('/bank-accounts/transactions/', { params }),
    get: (id) => api.get(`/bank-accounts/transactions/${id}/`),
    create: (data) => api.post('/bank-accounts/transactions/', data),
    update: (id, data) => api.put(`/bank-accounts/transactions/${id}/`, data),
    delete: (id) => api.delete(`/bank-accounts/transactions/${id}/`),
  },
};

export const transfersAPI = {
  list: (params) => api.get('/transfers/', { params }),
  get: (id) => api.get(`/transfers/${id}/`),
  create: (data) => api.post('/transfers/', data),
  update: (id, data) => api.put(`/transfers/${id}/`, data),
  delete: (id) => api.delete(`/transfers/${id}/`),
  approve: (id) => api.post(`/transfers/${id}/approve/`),
  statistics: () => api.get('/transfers/statistics/'),
};

export const installAPI = {
  status: () => api.get('/settings/setup-status/'),
  freshInstall: (data) => api.post('/settings/fresh-install/', data),
};

export const modulesAPI = {
  list: () => api.get('/settings/modules/'),
  get: (id) => api.get(`/settings/modules/${id}/`),
  update: (id, data) => api.put(`/settings/modules/${id}/`, data),
  patch: (id, data) => api.patch(`/settings/modules/${id}/`, data),
  applyPreset: (presetId) =>
    api.post('/settings/modules/apply-preset/', { preset_id: presetId }),
};

export const tenantsAPI = {
  list: (params) => api.get('/settings/tenants/', { params }),
  get: (id) => api.get(`/settings/tenants/${id}/`),
  create: (data) => api.post('/settings/tenants/', data),
  update: (id, data) => api.put(`/settings/tenants/${id}/`, data),
  delete: (id) => api.delete(`/settings/tenants/${id}/`),
  active: () => api.get('/settings/tenants/active/'),
  setCurrent: (id) => api.post(`/settings/tenants/${id}/set_current/`),
  clearCurrent: () => api.post('/settings/tenants/clear_current/'),
};

export const branchesAPI = {
  list: (params) => api.get('/settings/branches/', { params }),
  get: (id) => api.get(`/settings/branches/${id}/`),
  create: (data) => api.post('/settings/branches/', data),
  update: (id, data) => api.put(`/settings/branches/${id}/`, data),
  delete: (id) => api.delete(`/settings/branches/${id}/`),
  active: () => api.get('/settings/branches/active/'),
  headquarters: () => api.get('/settings/branches/headquarters/'),
  setCurrent: (id) => api.post(`/settings/branches/${id}/set_current/`),
  clearCurrent: () => api.post('/settings/branches/clear_current/'),
};

export const moduleFeaturesAPI = {
  list: (params) => api.get('/settings/module-features/', { params }),
  get: (id) => api.get(`/settings/module-features/${id}/`),
  update: (id, data) => api.put(`/settings/module-features/${id}/`, data),
  patch: (id, data) => api.patch(`/settings/module-features/${id}/`, data),
};

export const storeSettingsAPI = {
  get: () => api.get('/settings/store-settings/'),
  update: (data) => {
    if (data instanceof FormData) {
      return api.patch('/settings/store-settings/', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    }
    return api.patch('/settings/store-settings/', data);
  },
};

/** Per-module feature flags: GET/PATCH /api/settings/{module}/ */
export const moduleSettingsAPI = {
  get: (module) => api.get(`/settings/${module}/`),
  patch: (module, data) => api.patch(`/settings/${module}/`, data),
};

export const usersAPI = {
  list: (params) => api.get('/accounts/users/', { params }),
  get: (id) => api.get(`/accounts/users/${id}/`),
  create: (data) => api.post('/accounts/users/', data),
  update: (id, data) => api.put(`/accounts/users/${id}/`, data),
  delete: (id) => api.delete(`/accounts/users/${id}/`),
  search: (query) => api.get('/accounts/users/search/', { params: { q: query } }),
  assignRole: (id, roleId) => api.post(`/accounts/users/${id}/assign_role/`, { role_id: roleId }),
  changePassword: (id, newPassword) => api.post(`/accounts/users/${id}/change_password/`, { new_password: newPassword }),
};

export const rolesAPI = {
  list: (params) => api.get('/accounts/roles/', { params }),
  get: (id) => api.get(`/accounts/roles/${id}/`),
  create: (data) => api.post('/accounts/roles/', data),
  update: (id, data) => api.put(`/accounts/roles/${id}/`, data),
  delete: (id) => api.delete(`/accounts/roles/${id}/`),
  assignPermissions: (id, permissionIds) => api.post(`/accounts/roles/${id}/assign_permissions/`, { permission_ids: permissionIds }),
  users: (id) => api.get(`/accounts/roles/${id}/users/`),
};

export const permissionsAPI = {
  list: (params) => api.get('/accounts/permissions/', { params }),
  get: (id) => api.get(`/accounts/permissions/${id}/`),
  byModule: () => api.get('/accounts/permissions/by_module/'),
  byDomain: () => api.get('/accounts/permissions/by_domain/'),
};

export default api;

