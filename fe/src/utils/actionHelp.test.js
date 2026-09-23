import { ACTION_HELP, getActionHelp, saleCorrectionCompareItems } from './actionHelp';

describe('actionHelp', () => {
  it('returns known copy for refund and rollback', () => {
    expect(getActionHelp('sale_refund').shortLabel).toBe('Void / refund');
    expect(getActionHelp('sale_rollback').hover).toMatch(/should never have been recorded/i);
    expect(getActionHelp('sale_refund').contrast).toMatch(/Roll back/i);
    expect(getActionHelp('sale_rollback').contrast).toMatch(/Void \/ refund/i);
  });

  it('falls back to default', () => {
    expect(getActionHelp('unknown_key')).toEqual(ACTION_HELP.default);
    expect(getActionHelp()).toEqual(ACTION_HELP.default);
  });

  it('lists both sale corrections for compare panels', () => {
    const items = saleCorrectionCompareItems();
    expect(items).toHaveLength(2);
    expect(items[0].key).toBe('sale_refund');
    expect(items[1].key).toBe('sale_rollback');
    expect(items[0].body).toMatch(/customer returns/i);
    expect(items[1].body).toMatch(/duplicate checkout/i);
  });

  it('covers reject and approve education', () => {
    expect(getActionHelp('reject_change').confirmBody).toMatch(/Daily notes/i);
    expect(getActionHelp('approve_change').hover).toMatch(/live/i);
    expect(getActionHelp('sale_backfill').title).toMatch(/after the fact/i);
  });
});
