import {
  holdingNeedsRecoveryPrompt,
  countHoldingItems,
  countLocalDraftItems,
  localDraftNeedsRecoveryPrompt,
  buildCartRecoveryMessage,
  posCartDraftKey,
  serializeRetailCartDraft,
  loadRetailCartDraft,
  saveRetailCartDraft,
  clearRetailCartDraft,
  shouldPromptForHoldingRecovery,
  resolveBranchIdFromUser,
} from './posCartRecovery';

describe('posCartRecovery', () => {
  describe('holdingNeedsRecoveryPrompt', () => {
    it('returns true when holding has line items', () => {
      expect(
        holdingNeedsRecoveryPrompt({
          id: 9,
          sale_number: 'HOLD-001',
          items: [{ product_id: 1, quantity: 2 }],
        })
      ).toBe(true);
    });

    it('returns false for empty holding or no holding', () => {
      expect(holdingNeedsRecoveryPrompt(null)).toBe(false);
      expect(holdingNeedsRecoveryPrompt({ items: [] })).toBe(false);
      expect(
        holdingNeedsRecoveryPrompt({ items: [{ quantity: 0 }] })
      ).toBe(false);
    });
  });

  describe('countHoldingItems', () => {
    it('sums line quantities', () => {
      expect(
        countHoldingItems({
          items: [{ quantity: 2 }, { quantity: 3 }],
        })
      ).toBe(5);
    });
  });

  describe('localDraftNeedsRecoveryPrompt', () => {
    it('returns true when draft has cart lines', () => {
      expect(
        localDraftNeedsRecoveryPrompt({
          cart: [{ id: 1, quantity: 1 }],
          savedAt: Date.now(),
        })
      ).toBe(true);
    });

    it('returns false for stale or empty drafts', () => {
      expect(localDraftNeedsRecoveryPrompt(null)).toBe(false);
      expect(localDraftNeedsRecoveryPrompt({ cart: [] })).toBe(false);
      expect(
        localDraftNeedsRecoveryPrompt({
          cart: [{ id: 1, quantity: 1 }],
          savedAt: Date.now() - 8 * 24 * 60 * 60 * 1000,
        })
      ).toBe(false);
    });
  });

  describe('buildCartRecoveryMessage', () => {
    it('mentions invoice number for holding drafts', () => {
      const msg = buildCartRecoveryMessage({
        source: 'holding',
        itemCount: 3,
        label: 'HOLD-42',
      });
      expect(msg).toMatch(/3 item/i);
      expect(msg).toMatch(/HOLD-42/);
    });

    it('describes local retail draft', () => {
      const msg = buildCartRecoveryMessage({
        source: 'local',
        itemCount: 2,
      });
      expect(msg).toMatch(/2 item/i);
      expect(msg).toMatch(/continue/i);
    });
  });

  describe('shouldPromptForHoldingRecovery', () => {
    it('is alias for holding with items', () => {
      expect(
        shouldPromptForHoldingRecovery({
          items: [{ quantity: 1 }],
        })
      ).toBe(true);
    });
  });

  describe('countLocalDraftItems', () => {
    it('sums cart line quantities', () => {
      expect(
        countLocalDraftItems({
          cart: [{ quantity: 2 }, { quantity: 1 }],
        })
      ).toBe(3);
    });
  });

  describe('resolveBranchIdFromUser', () => {
    it('reads branch id from profile object or scalar', () => {
      expect(
        resolveBranchIdFromUser({ id: 1, profile: { branch: { id: 9 } } })
      ).toBe(9);
      expect(resolveBranchIdFromUser({ profile: { branch_id: 4 } })).toBe(4);
      expect(resolveBranchIdFromUser(null)).toBeNull();
    });
  });

  describe('serializeRetailCartDraft', () => {
    it('stamps savedAt and version', () => {
      const draft = serializeRetailCartDraft({ cart: [{ id: 1, quantity: 1 }] });
      expect(draft.version).toBe(1);
      expect(draft.savedAt).toBeGreaterThan(0);
    });
  });

  describe('retail cart draft storage', () => {
    const storage = {};

    beforeEach(() => {
      Object.keys(storage).forEach((k) => delete storage[k]);
      global.sessionStorage = {
        getItem: (k) => storage[k] ?? null,
        setItem: (k, v) => {
          storage[k] = v;
        },
        removeItem: (k) => {
          delete storage[k];
        },
      };
    });

    it('round-trips cart draft under user/branch key', () => {
      const key = posCartDraftKey(7, 3);
      const draft = serializeRetailCartDraft({
        cart: [{ id: 5, name: 'Webbing', quantity: 2, price: 500 }],
        selectedCustomer: { id: 'walk-in', name: 'Walk-in' },
        taxPct: 16,
        discount: 0,
      });
      saveRetailCartDraft(key, draft);
      const loaded = loadRetailCartDraft(key);
      expect(loaded.cart).toHaveLength(1);
      expect(loaded.cart[0].id).toBe(5);
      clearRetailCartDraft(key);
      expect(loadRetailCartDraft(key)).toBeNull();
    });

    it('returns null for invalid json', () => {
      const key = posCartDraftKey(1, 1);
      sessionStorage.setItem(key, '{not json');
      expect(loadRetailCartDraft(key)).toBeNull();
    });

    it('returns null for unknown draft version', () => {
      const key = posCartDraftKey(2, 2);
      sessionStorage.setItem(key, JSON.stringify({ version: 2, cart: [] }));
      expect(loadRetailCartDraft(key)).toBeNull();
    });

    it('save ignores storage failures', () => {
      const key = posCartDraftKey(3, 3);
      const failing = {
        setItem: () => {
          throw new Error('quota');
        },
      };
      expect(() =>
        saveRetailCartDraft(key, serializeRetailCartDraft({ cart: [] }), failing)
      ).not.toThrow();
    });
  });
});
