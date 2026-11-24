/**
 * Merge role-package lines with personal assignments for one employee.
 *
 * Personal assignment wins for the same component. Amount ``0`` means this
 * person no longer gets that package amount (removed for them only).
 */

/**
 * @param {object|null|undefined} rolePackage Package detail with ``lines``.
 * @param {Array<object>} assignments Personal ``EmployeePayAssignment`` rows.
 * @returns {Array<object>} Display rows for the Staff pay inherited table.
 */
export function mergeInheritedPayLines(rolePackage, assignments = []) {
  const personal = Array.isArray(assignments) ? assignments : [];
  const byComponent = new Map(
    personal
      .filter((row) => row && row.component != null)
      .map((row) => [Number(row.component), row]),
  );
  const lines = (rolePackage?.lines || []).filter((line) => line?.is_active !== false);
  return lines.map((line) => {
    const override = byComponent.get(Number(line.component)) || null;
    const packageAmount = line.amount == null ? null : String(line.amount);
    const packageRate = line.rate == null ? null : String(line.rate);
    const personalAmount =
      override && override.amount != null ? String(override.amount) : null;
    const personalRate =
      override && override.rate != null ? String(override.rate) : null;
    const removed =
      Boolean(override) &&
      override.amount != null &&
      Number(override.amount) === 0 &&
      (override.rate == null || override.rate === '' || Number(override.rate) === 0);
    return {
      packageLineId: line.id,
      componentId: line.component,
      componentName: line.component_name || line.component_code || 'Component',
      componentCode: line.component_code || '',
      packageAmount,
      packageRate,
      override,
      personalAmount,
      personalRate,
      removed,
      effectiveAmount: removed
        ? '0'
        : personalAmount != null
          ? personalAmount
          : packageAmount,
      effectiveRate: removed
        ? null
        : personalRate != null
          ? personalRate
          : packageRate,
      status: removed
        ? 'removed'
        : override
          ? 'edited'
          : 'inherited',
    };
  });
}

/**
 * Payload to set / clear a personal amount for one package component.
 *
 * @param {object} args
 * @param {number|string} args.employeeId Employee PK.
 * @param {number|string} args.componentId Pay component PK.
 * @param {string|number|null} args.amount Fixed amount; ``0`` removes package money.
 * @param {string|number|null} [args.rate] Optional rate override.
 * @param {string} [args.notes] Optional note, max 255 chars.
 * @returns {object} Body for createAssignment.
 */
export function personalPackageOverridePayload({
  employeeId,
  componentId,
  amount,
  rate = null,
  notes = '',
}) {
  return {
    employee: Number(employeeId),
    component: Number(componentId),
    amount: amount === '' || amount == null ? null : amount,
    rate: rate === '' || rate == null ? null : rate,
    notes: String(notes || '').slice(0, 255),
    is_active: true,
  };
}
