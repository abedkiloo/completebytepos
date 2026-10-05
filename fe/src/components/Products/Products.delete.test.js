import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import Products from './Products';
import { productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { installLocalStorageMock } from '../../test-utils';

jest.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });

jest.mock('../../services/api', () => ({
  productsAPI: {
    list: jest.fn(),
    statistics: jest.fn(),
    delete: jest.fn(),
    bulkDelete: jest.fn(),
  },
  categoriesAPI: { list: () => Promise.resolve({ data: [] }) },
  variantsAPI: { list: () => Promise.resolve({ data: [] }) },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn(), info: jest.fn() },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({ settings: { maker_checker_enabled: true }, loading: false }),
}));

jest.mock('../../hooks/useModuleSettings', () => ({
  useModuleSettings: () => ({ settings: {}, meta: null, loading: false }),
}));

jest.mock('../../utils/navAccess', () => ({
  getPersonaFromStorage: () => 'manager',
}));

jest.mock('../ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }) => (
    <button type="button" onClick={onClick}>{children}</button>
  ),
  DropdownMenuLabel: ({ children }) => <div>{children}</div>,
  DropdownMenuSeparator: () => null,
}));

jest.mock('./ProductForm', () => () => null);
jest.mock('./ProductDetailPanel', () => () => null);
jest.mock('../Inventory/StockCountModal', () => () => null);
jest.mock('../Approvals/PendingApprovalBadges', () => () => null);
jest.mock('../page', () => ({
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ actions }) => <div>{actions}</div>,
  ListPaginationRail: ({ children }) => <div>{children}</div>,
}));

const product = {
  id: 5,
  name: 'Sugar 2kg',
  sku: 'SUG-2',
  price: '200',
  selling_price: '200',
  cost: '150',
  stock_quantity: 0,
  track_stock: false,
  is_active: true,
};

function signInAs(role) {
  localStorage.setItem('user', JSON.stringify({ id: 1 }));
  localStorage.setItem('profile', JSON.stringify({ role }));
}

describe('Products permanent delete', () => {
  beforeEach(() => {
    installLocalStorageMock();
    jest.clearAllMocks();
    productsAPI.list.mockResolvedValue({ data: { results: [product], count: 1 } });
    productsAPI.statistics.mockResolvedValue({ data: {} });
  });

  it('hides delete from non-admins', async () => {
    signInAs('manager');
    render(<Products />);
    expect(await screen.findByText('Sugar 2kg')).toBeInTheDocument();
    expect(screen.queryByText('Delete product')).not.toBeInTheDocument();
  });

  it('lets an admin permanently delete an item added in error', async () => {
    signInAs('admin');
    productsAPI.delete.mockResolvedValue({ status: 204 });
    render(<Products />);
    fireEvent.click(await screen.findByText('Delete product'));
    expect(screen.getByText(/removed for good and cannot be undone/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => expect(productsAPI.delete).toHaveBeenCalledWith(5));
    expect(toast.success).toHaveBeenCalledWith('Product permanently deleted');
  });

  it('tells the admin why a product in use cannot be deleted', async () => {
    signInAs('admin');
    const reason =
      '"Sugar 2kg" cannot be deleted because it still has 4 in stock. Deactivate it instead.';
    productsAPI.delete.mockRejectedValue({ response: { status: 400, data: { error: reason } } });
    render(<Products />);
    fireEvent.click(await screen.findByText('Delete product'));
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(reason));
  });
});
