import { handleSaleBackfillResponse } from './saleBackfill';

describe('handleSaleBackfillResponse', () => {
  it('calls onPending for 202 responses', () => {
    const onPending = jest.fn();
    const onApplied = jest.fn();
    const pending = { id: 1 };

    const result = handleSaleBackfillResponse(
      { status: 202, data: { pending_change: pending } },
      { onPending, onApplied }
    );

    expect(result).toBe('pending');
    expect(onPending).toHaveBeenCalledWith(pending, { pending_change: pending });
    expect(onApplied).not.toHaveBeenCalled();
  });

  it('calls onApplied for immediate create responses', () => {
    const onPending = jest.fn();
    const onApplied = jest.fn();
    const sale = { sale_number: 'S-1' };

    const result = handleSaleBackfillResponse({ status: 201, data: sale }, { onPending, onApplied });

    expect(result).toBe('applied');
    expect(onApplied).toHaveBeenCalledWith(sale);
    expect(onPending).not.toHaveBeenCalled();
  });

  it('tolerates missing callbacks', () => {
    expect(handleSaleBackfillResponse({ status: 201, data: {} })).toBe('applied');
    expect(handleSaleBackfillResponse({ status: 202, data: {} })).toBe('pending');
  });
});
