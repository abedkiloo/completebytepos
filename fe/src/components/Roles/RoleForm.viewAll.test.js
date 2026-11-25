import React from 'react';
import { render, screen } from '@testing-library/react';
import RoleForm from './RoleForm';

jest.mock('../../services/api', () => ({
  rolesAPI: {
    create: jest.fn(),
    update: jest.fn(),
  },
}));

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: () => ({ settings: {} }),
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

describe('RoleForm sales.view_all label', () => {
  it('shows the human description for view other staff sales', () => {
    const permissions = [
      {
        id: 1,
        module: 'sales',
        action: 'view_all',
        name: 'sales.view_all',
        description:
          'View other staff sales (not only your own — history, daily, dashboard)',
        action_display: "View others' records",
      },
    ];
    const permissionCatalog = [
      {
        id: 'commerce',
        label: 'Commerce',
        modules: [
          {
            id: 'sales',
            label: 'Sales',
            permissions,
          },
        ],
      },
    ];

    render(
      <RoleForm
        role={null}
        permissions={permissions}
        permissionCatalog={permissionCatalog}
        showPermissionCatalog
        onClose={jest.fn()}
      />
    );

    expect(screen.getByTestId('perm-sales-view_all')).toHaveTextContent(
      /View other staff sales/i
    );
  });
});
