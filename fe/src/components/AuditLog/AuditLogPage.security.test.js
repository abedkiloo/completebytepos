import React from 'react';
import { render, screen } from '@testing-library/react';
import AuditLogPage from './AuditLogPage';

jest.mock('../../services/api', () => ({
  auditLogAPI: {
    list: jest.fn(),
    get: jest.fn(),
    facets: jest.fn(),
  },
  usersAPI: {
    list: jest.fn(),
  },
}));

const mockMayEdit = jest.fn();

jest.mock('../../utils/roleAccess', () => ({
  userMayEditFinancialFieldsFromStorage: () => mockMayEdit(),
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));

jest.mock('react-router-dom', () => ({
  Navigate: ({ to }) => <div data-testid="redirect">redirect:{to}</div>,
}));

jest.mock('lucide-react', () => ({
  ScrollText: () => null,
  Search: () => null,
  Loader2: () => null,
}));

jest.mock('../page', () => ({
  PageShell: ({ children }) => <div>{children}</div>,
  PageHeader: ({ title }) => <h1>{title}</h1>,
  PageLoading: () => <div>loading</div>,
}));

jest.mock('../page/ListSortBar', () => ({
  ListSortBar: () => null,
}));

jest.mock('../ui/card', () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}));

jest.mock('../ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

jest.mock('../ui/button', () => ({
  Button: ({ children, ...props }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

jest.mock('../ui/badge', () => ({
  Badge: ({ children }) => <span>{children}</span>,
}));

jest.mock('../ui/dialog', () => ({
  Dialog: () => null,
  DialogContent: () => null,
  DialogHeader: () => null,
  DialogTitle: () => null,
  DialogDescription: () => null,
}));

jest.mock('../../hooks/useListOrdering', () => ({
  useListOrdering: () => ({ ordering: '-created_at', setOrdering: jest.fn() }),
}));

jest.mock('../../utils/listOrdering', () => ({
  withListOrdering: (params) => params,
}));

jest.mock('../../utils/formatters', () => ({
  formatDateTime: (v) => String(v),
}));

jest.mock('../../lib/cn', () => ({
  cn: (...args) => args.filter(Boolean).join(' '),
}));

describe('AuditLogPage security', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('denies users without financial edit access', () => {
    mockMayEdit.mockReturnValue(false);
    render(<AuditLogPage />);
    expect(screen.getByTestId('redirect')).toHaveTextContent('redirect:/');
    expect(screen.queryByText('Audit log')).not.toBeInTheDocument();
  });
});
