import {
  mergeInheritedPayLines,
  personalPackageOverridePayload,
} from './staffPayLines';

describe('staffPayLines', () => {
  const rolePackage = {
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
      {
        id: 12,
        component: 4,
        component_name: 'Housing',
        component_code: 'ALLOWANCE_HOUSING',
        amount: '5000.00',
        rate: null,
        is_active: true,
      },
      {
        id: 13,
        component: 5,
        component_name: 'Old',
        component_code: 'OLD',
        amount: '1.00',
        is_active: false,
      },
    ],
  };

  it('unit: merges inherited package lines with personal edits', () => {
    const rows = mergeInheritedPayLines(rolePackage, [
      { id: 99, component: 3, amount: '4000.00', rate: null },
    ]);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      componentId: 3,
      status: 'edited',
      packageAmount: '2500.00',
      personalAmount: '4000.00',
      effectiveAmount: '4000.00',
    });
    expect(rows[1].status).toBe('inherited');
  });

  it('corrected: amount 0 marks the package line removed for that person', () => {
    const rows = mergeInheritedPayLines(rolePackage, [
      { id: 1, component: 4, amount: '0', rate: null },
    ]);
    expect(rows[1]).toMatchObject({
      status: 'removed',
      removed: true,
      effectiveAmount: '0',
    });
  });

  it('security: blank package and non-array assignments stay empty', () => {
    expect(mergeInheritedPayLines(null, null)).toEqual([]);
    expect(mergeInheritedPayLines({}, undefined)).toEqual([]);
  });

  it('module: override payload pins employee and component ids', () => {
    expect(
      personalPackageOverridePayload({
        employeeId: '7',
        componentId: '3',
        amount: '0',
        notes: 'Removed from role package for this employee',
      }),
    ).toEqual({
      employee: 7,
      component: 3,
      amount: '0',
      rate: null,
      notes: 'Removed from role package for this employee',
      is_active: true,
    });
  });

  it('stress: many package lines merge without throwing', () => {
    const big = {
      lines: Array.from({ length: 80 }, (_, i) => ({
        id: i + 1,
        component: i + 1,
        component_name: `Line ${i}`,
        component_code: `C${i}`,
        amount: String(i * 10),
        is_active: true,
      })),
    };
    const assignments = Array.from({ length: 40 }, (_, i) => ({
      id: 1000 + i,
      component: i + 1,
      amount: i % 2 === 0 ? '0' : String(i * 100),
    }));
    const rows = mergeInheritedPayLines(big, assignments);
    expect(rows).toHaveLength(80);
    expect(rows.filter((r) => r.status === 'removed')).toHaveLength(20);
  });
});
