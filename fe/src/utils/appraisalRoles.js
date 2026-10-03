const APPRAISAL_ADMIN_ROLES = new Set(['super admin', 'admin', 'administrator']);

export function isAppraisalAdminRole(name) {
  return APPRAISAL_ADMIN_ROLES.has(String(name || '').trim().toLowerCase());
}

export function roleHasPersonalTarget(name) {
  return !isAppraisalAdminRole(name);
}

export function filterRoleDailyTargets(targets) {
  return Object.fromEntries(
    Object.entries(targets || {}).filter(([role]) => roleHasPersonalTarget(role))
  );
}
