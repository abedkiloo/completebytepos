/**
 * Group module setting rows by label prefix for clearer System Settings UI.
 */

const GROUP_ORDER = ['general', 'sales', 'managers'];

const GROUP_LABELS = {
  general: 'General',
  sales: 'Sales staff',
  managers: 'Managers & admins',
};

export function stripSettingLabelPrefix(label) {
  if (!label) return label;
  return label.replace(/^(Sales|Managers):\s*/i, '').trim();
}

export function groupModuleSettings(entries) {
  const buckets = { general: [], sales: [], managers: [] };
  for (const [key, item] of entries) {
    const label = item?.label || key;
    if (/^Sales:/i.test(label)) {
      buckets.sales.push([key, item]);
    } else if (/^Managers:/i.test(label)) {
      buckets.managers.push([key, item]);
    } else {
      buckets.general.push([key, item]);
    }
  }
  return GROUP_ORDER.filter((id) => buckets[id].length > 0).map((id) => ({
    id,
    label: GROUP_LABELS[id],
    items: buckets[id],
  }));
}
