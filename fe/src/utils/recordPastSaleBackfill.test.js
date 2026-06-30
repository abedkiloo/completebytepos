import {
  defaultOccurredAtLocal,
  minOccurredAtLocal,
  toIsoDatetime,
  localDatetimeFromIso,
  resolveBackfillServedById,
  servedByIdForPrefill,
  canResubmitBackfillChange,
  parseRejectedBackfillChange,
  buildBackfillSubmitPayload,
  backfillPendingNavigatePath,
  backfillPendingToastMessage,
  backfillRejectionSuccessMessage,
  linesFromBackfillPayload,
} from './recordPastSaleBackfill';

describe('recordPastSaleBackfill', () => {
  const fixedNow = new Date('2026-06-24T12:00:00.000Z');

  describe('datetime helpers', () => {
    it('defaultOccurredAtLocal returns local datetime string', () => {
      const value = defaultOccurredAtLocal(fixedNow);
      expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    });

    it('minOccurredAtLocal subtracts maxDays', () => {
      const min = minOccurredAtLocal(30, fixedNow);
      const max = defaultOccurredAtLocal(fixedNow);
      expect(min < max).toBe(true);
    });

    it('toIsoDatetime converts local input to ISO', () => {
      const iso = toIsoDatetime('2026-06-20T10:30');
      expect(iso).toContain('2026-06-20');
    });

    it('toIsoDatetime returns null for empty or invalid values', () => {
      expect(toIsoDatetime('')).toBeNull();
      expect(toIsoDatetime('not-a-date')).toBeNull();
    });

    it('localDatetimeFromIso maps ISO to datetime-local', () => {
      const local = localDatetimeFromIso('2026-06-20T07:30:00.000Z', fixedNow);
      expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    });

    it('localDatetimeFromIso falls back when iso missing or invalid', () => {
      expect(localDatetimeFromIso(null, fixedNow)).toBe(defaultOccurredAtLocal(fixedNow));
      expect(localDatetimeFromIso('bad', fixedNow)).toBe(defaultOccurredAtLocal(fixedNow));
    });
  });

  describe('served by', () => {
    it('forces current user for staff', () => {
      expect(
        resolveBackfillServedById({
          canPickServedBy: false,
          servedById: '99',
          currentUserId: 5,
        })
      ).toBe(5);
    });

    it('allows manager to pick another staff member', () => {
      expect(
        resolveBackfillServedById({
          canPickServedBy: true,
          servedById: '12',
          currentUserId: 5,
        })
      ).toBe(12);
    });

    it('defaults manager to self when servedById empty', () => {
      expect(
        resolveBackfillServedById({
          canPickServedBy: true,
          servedById: '',
          currentUserId: 5,
        })
      ).toBe(5);
    });

    it('servedByIdForPrefill respects role', () => {
      expect(
        servedByIdForPrefill({
          canPickServedBy: false,
          payloadServedById: 99,
          currentUserId: 5,
        })
      ).toBe('5');
      expect(
        servedByIdForPrefill({
          canPickServedBy: true,
          payloadServedById: 99,
          currentUserId: 5,
        })
      ).toBe('99');
    });

    it('servedByIdForPrefill returns empty when no current user', () => {
      expect(
        servedByIdForPrefill({
          canPickServedBy: false,
          payloadServedById: 99,
          currentUserId: null,
        })
      ).toBe('');
    });

    it('parseRejectedBackfillChange keeps manager served-by selection', () => {
      const parsed = parseRejectedBackfillChange(
        {
          id: 1,
          status: 'rejected',
          action_type: 'sale_backfill',
          apply_payload: { served_by_id: 8, items: [] },
        },
        { canPickServedBy: true, currentUserId: 5 }
      );
      expect(parsed.prefill.servedById).toBe('8');
    });
  });

  describe('rejected resubmit parsing', () => {
    const rejectedChange = {
      id: 42,
      status: 'rejected',
      action_type: 'sale_backfill',
      rejection_reason: 'Wrong date',
      reason: 'Original reason text',
      apply_payload: {
        occurred_at: '2026-06-20T10:00:00.000Z',
        backfill_reason: 'Offline sale',
        sale_type: 'pos',
        payment_method: 'cash',
        amount_paid: '100',
        served_by_id: 8,
        items: [{ product_id: 1, quantity: 1, unit_price: '100' }],
      },
    };

    it('canResubmitBackfillChange accepts rejected sale_backfill only', () => {
      expect(canResubmitBackfillChange(rejectedChange)).toBe(true);
      expect(canResubmitBackfillChange({ ...rejectedChange, status: 'pending' })).toBe(false);
      expect(canResubmitBackfillChange({ ...rejectedChange, action_type: 'product_price' })).toBe(
        false
      );
    });

    it('parseRejectedBackfillChange returns prefill for valid submission', () => {
      const parsed = parseRejectedBackfillChange(rejectedChange, {
        canPickServedBy: false,
        currentUserId: 5,
      });
      expect(parsed.ok).toBe(true);
      expect(parsed.resubmitPendingId).toBe(42);
      expect(parsed.rejectionReason).toBe('Wrong date');
      expect(parsed.prefill.backfillReason).toBe('Offline sale');
      expect(parsed.prefill.servedById).toBe('5');
    });

    it('parseRejectedBackfillChange rejects invalid submission', () => {
      const parsed = parseRejectedBackfillChange({ status: 'approved' });
      expect(parsed.ok).toBe(false);
      expect(parsed.error).toMatch(/cannot be edited/i);
    });
  });

  describe('buildBackfillSubmitPayload', () => {
    const base = {
      occurredAt: '2026-06-20T10:30',
      backfillReason: '  Sold offline during outage  ',
      saleType: 'pos',
      canPickServedBy: false,
      servedById: '99',
      currentUserId: 5,
      customerId: '',
      paymentMethod: 'cash',
      paymentReference: '',
      amountPaid: '50',
      allowPartial: false,
      ackStockWarnings: true,
      lines: [{ product_id: 1, variant_id: null, quantity: 2, unit_price: 25 }],
      resubmitPendingId: null,
    };

    it('builds payload with forced served_by for staff', () => {
      const payload = buildBackfillSubmitPayload(base);
      expect(payload.served_by_id).toBe(5);
      expect(payload.backfill_reason).toBe('Sold offline during outage');
      expect(payload.items).toHaveLength(1);
      expect(payload.resubmit_of).toBeUndefined();
    });

    it('includes resubmit_of and invoice flag when applicable', () => {
      const payload = buildBackfillSubmitPayload({
        ...base,
        saleType: 'normal',
        canPickServedBy: true,
        servedById: '8',
        resubmitPendingId: 42,
      });
      expect(payload.resubmit_of).toBe(42);
      expect(payload.create_invoice).toBe(true);
      expect(payload.served_by_id).toBe(8);
    });
  });

  describe('navigation, toast, and rejection copy', () => {
    it('backfillPendingNavigatePath routes resubmits back to form', () => {
      expect(backfillPendingNavigatePath(42)).toBe('/sales/record-past');
      expect(backfillPendingNavigatePath(null)).toBe('/pending-approvals');
    });

    it('backfillPendingToastMessage uses correction copy for resubmit', () => {
      expect(backfillPendingToastMessage(42, 'Queued')).toBe(
        'Corrected sale sent back for approval.'
      );
      expect(backfillPendingToastMessage(null, 'Queued')).toBe('Queued');
    });

    it('backfillRejectionSuccessMessage guides makers for sale_backfill', () => {
      expect(backfillRejectionSuccessMessage('sale_backfill')).toBe(
        'Rejected — sent back to staff to fix on Record past sale.'
      );
      expect(backfillRejectionSuccessMessage('product_price')).toBe(
        'Rejected — nothing was changed'
      );
    });
  });

  describe('linesFromBackfillPayload', () => {
    it('resolves product name and sku', async () => {
      const lines = await linesFromBackfillPayload(
        [{ product_id: 1, quantity: 1, unit_price: '10' }],
        {
          getProduct: async () => ({ id: 1, name: 'Pen', sku: 'PEN-1' }),
          getVariants: async () => [],
          getVariantRowLabel: () => '',
        }
      );
      expect(lines[0].product_name).toBe('Pen (PEN-1)');
    });

    it('resolves variant label when variant_id present', async () => {
      const lines = await linesFromBackfillPayload(
        [{ product_id: 1, variant_id: 9, quantity: 1, unit_price: '10' }],
        {
          getProduct: async () => ({ id: 1, name: 'Shirt' }),
          getVariants: async () => [{ id: 9, size_name: 'L', color_name: 'Blue' }],
          getVariantRowLabel: (v) => `${v.size_name}/${v.color_name}`,
        }
      );
      expect(lines[0].product_name).toBe('Shirt — L/Blue');
    });

    it('keeps fallback label when product fetch fails', async () => {
      const lines = await linesFromBackfillPayload(
        [{ product_id: 77, quantity: 1, unit_price: '5' }],
        {
          getProduct: async () => {
            throw new Error('missing');
          },
          getVariants: async () => [],
          getVariantRowLabel: () => '',
        }
      );
      expect(lines[0].product_name).toBe('Product #77');
    });

    it('requires fetch dependencies', async () => {
      await expect(linesFromBackfillPayload([])).rejects.toThrow(/requires product fetch/i);
    });
  });
});
