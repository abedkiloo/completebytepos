/**
 * Smoke: Products.js must parse and export a component (catches duplicate
 * const declarations and other syntax errors that break production builds).
 */

jest.mock('../../services/api', () => ({
  productsAPI: {
    list: jest.fn(() => Promise.resolve({ data: { results: [], count: 0 } })),
    statistics: jest.fn(() => Promise.resolve({ data: {} })),
    exportCsv: jest.fn(),
    importCsv: jest.fn(),
  },
  categoriesAPI: {
    list: jest.fn(() => Promise.resolve({ data: [] })),
  },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(() => ({
    settings: {
      maker_checker_enabled: false,
      allow_sales_add_products: true,
      sales_catalog_skip_pricing: false,
    },
    loading: false,
  })),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: jest.fn(() => ({
    settings: {},
    meta: null,
    loading: false,
  })),
}));

jest.mock('../../utils/navAccess', () => ({
  getPersonaFromStorage: jest.fn(() => 'manager'),
}));

jest.mock('../../utils/roleAccess', () => ({
  PERSONA: { SALES: 'sales', MANAGER: 'manager', SUPER_ADMIN: 'super_admin' },
  userMayEditFinancialFieldsFromStorage: jest.fn(() => true),
}));

jest.mock('./ProductForm', () => () => null);
jest.mock('../ConfirmDialog/ConfirmDialog', () => () => null);
jest.mock('../Approvals/ChangeReasonField', () => () => null);
jest.mock('../Approvals/PendingApprovalBadges', () => () => null);
jest.mock('../page', () => ({
  PageShell: ({ children }) => children,
  PageHeader: ({ children }) => children,
}));

describe('Products module', () => {
  it('parses and exports the Products component', () => {
    const Products = require('./Products').default;
    expect(typeof Products).toBe('function');
  });
});
