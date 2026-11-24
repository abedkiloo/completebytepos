import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import StaffPayPanel from './StaffPayPanel';
import { employeesAPI, payrollAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  employeesAPI: {
    list: jest.fn(),
  },
  payrollAPI: {
    listAssignments: jest.fn(),
    createAssignment: jest.fn(),
    updateAssignment: jest.fn(),
    deleteAssignment: jest.fn(),
    listPackages: jest.fn(),
    getPackage: jest.fn(),
    packageStaffOverview: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const COMPONENTS = [
  {
    id: 3,
    code: 'ALLOWANCE_TRANSPORT',
    name: 'Transport',
    kind: 'earning',
    is_active: true,
    is_statutory: false,
  },
  {
    id: 9,
    code: 'ALLOWANCE_MEAL',
    name: 'Meal',
    kind: 'earning',
    is_active: true,
    is_statutory: false,
  },
];

describe('StaffPayPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    employeesAPI.list.mockResolvedValue({
      data: {
        results: [
          {
            id: 7,
            employee_id: 'E-7',
            first_name: 'Pat',
            last_name: 'Sales',
            full_name: 'Pat Sales',
            role_id: 2,
            role_name: 'Sales Personnel',
            position: 'Sales Personnel',
            salary: '20000.00',
          },
        ],
      },
    });
    payrollAPI.listAssignments.mockResolvedValue({ data: { results: [] } });
    payrollAPI.listPackages.mockResolvedValue({
      data: {
        results: [
          {
            id: 5,
            role: 2,
            role_name: 'Sales Personnel',
            name: 'Sales package',
            is_active: true,
          },
        ],
      },
    });
    payrollAPI.getPackage.mockResolvedValue({
      data: {
        id: 5,
        role: 2,
        role_name: 'Sales Personnel',
        name: 'Sales package',
        display_name: 'Sales package',
        lines: [
          {
            id: 11,
            component: 3,
            component_name: 'Transport',
            component_code: 'ALLOWANCE_TRANSPORT',
            amount: '2500.00',
            rate: null,
            is_active: true,
          },
        ],
      },
    });
    payrollAPI.packageStaffOverview.mockResolvedValue({
      data: {
        results: [
          {
            id: 7,
            effective_basic: '20000.00',
            estimated_gross: '22500.00',
            estimated_net: '22500.00',
            role_name: 'Sales Personnel',
            package_name: 'Sales package',
          },
        ],
      },
    });
    payrollAPI.createAssignment.mockResolvedValue({ data: { id: 50 } });
    payrollAPI.deleteAssignment.mockResolvedValue({});
  });

  async function openEmployeePay() {
    render(<StaffPayPanel components={COMPONENTS} initialEmployeeId="7" />);
    await waitFor(() => expect(payrollAPI.listPackages).toHaveBeenCalled());
    await waitFor(() => expect(payrollAPI.getPackage).toHaveBeenCalledWith(5));
    expect(await screen.findByText(/Package lines for/i)).toBeInTheDocument();
  }

  it('integration: edit package amount for one employee', async () => {
    await openEmployeePay();
    expect(screen.getByText('Transport')).toBeInTheDocument();
    expect(screen.getByText('Inherited')).toBeInTheDocument();

    fireEvent.blur(screen.getByLabelText('Amount for Transport'), {
      target: { value: '4000' },
    });
    await waitFor(() =>
      expect(payrollAPI.createAssignment).toHaveBeenCalledWith(
        expect.objectContaining({
          employee: 7,
          component: 3,
          amount: '4000',
        }),
      ),
    );
  });

  it('integration: remove package amount for one employee', async () => {
    await openEmployeePay();
    fireEvent.click(screen.getByRole('button', { name: /Remove Transport for this employee/i }));
    await waitFor(() =>
      expect(payrollAPI.createAssignment).toHaveBeenCalledWith(
        expect.objectContaining({
          employee: 7,
          component: 3,
          amount: '0',
          notes: expect.stringMatching(/Removed from role package/i),
        }),
      ),
    );
  });

  it('corrected: restore package amount deletes the personal override', async () => {
    payrollAPI.listAssignments.mockResolvedValue({
      data: {
        results: [
          {
            id: 88,
            component: 3,
            component_name: 'Transport',
            component_code: 'ALLOWANCE_TRANSPORT',
            amount: '0.00',
            rate: null,
            notes: 'Removed from role package for this employee',
          },
        ],
      },
    });
    await openEmployeePay();
    expect(screen.getByText('Removed')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Restore package/i }));
    await waitFor(() => expect(payrollAPI.deleteAssignment).toHaveBeenCalledWith(88));
  });
});
