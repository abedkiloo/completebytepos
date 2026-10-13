/**
 * Apply a single field or a patch of fields to customer form state.
 * Used so Kenya county → sub-county → ward cascades update atomically.
 */
export function applyCustomerFormFieldUpdate(prev, keyOrPatch, value) {
  if (keyOrPatch != null && typeof keyOrPatch === 'object' && !Array.isArray(keyOrPatch)) {
    return { ...prev, ...keyOrPatch };
  }
  return { ...prev, [keyOrPatch]: value };
}
