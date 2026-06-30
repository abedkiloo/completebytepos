import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock, Download, Plus, Search, Trash2, Upload, X } from 'lucide-react';
import { customersAPI, productsAPI, salesAPI, usersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { handleSaleBackfillResponse } from '../../utils/saleBackfill';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { makerCheckerReasonCopy } from '../../utils/makerChecker';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { isMakerCheckerEnabled, getCurrentUserId } from '../../utils/makerChecker';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { PageHeader, PageShell } from '../page';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import VariantSelector from '../POS/VariantSelector';
import { shouldOpenVariantPicker, getVariantRowLabel } from '../../utils/variantSelector';

function selectValue(setter) {
  return (e) => setter(e.target.value);
}

function defaultOccurredAtLocal() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function minOccurredAtLocal(maxDays) {
  const d = new Date();
  d.setDate(d.getDate() - maxDays);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function toIsoDatetime(localValue) {
  if (!localValue) return null;
  const d = new Date(localValue);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

function SinglePastSaleForm({ maxDays, mcOn, mcBackfill, backfillCopy }) {
  const navigate = useNavigate();
  const currentUserId = getCurrentUserId();
  const [occurredAt, setOccurredAt] = useState(defaultOccurredAtLocal);
  const [backfillReason, setBackfillReason] = useState('');
  const [saleType, setSaleType] = useState('pos');
  const [servedById, setServedById] = useState(
    currentUserId != null ? String(currentUserId) : ''
  );
  const [customerId, setCustomerId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [paymentReference, setPaymentReference] = useState('');
  const [amountPaid, setAmountPaid] = useState('');
  const [allowPartial, setAllowPartial] = useState(false);
  const [lines, setLines] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [productSearch, setProductSearch] = useState('');
  const [productResults, setProductResults] = useState([]);
  const [searchingProducts, setSearchingProducts] = useState(false);
  const [customerOptions, setCustomerOptions] = useState([]);
  const [staffOptions, setStaffOptions] = useState([]);
  const [pickQty, setPickQty] = useState('1');
  const [variantPickerProduct, setVariantPickerProduct] = useState(null);
  const [pendingQty, setPendingQty] = useState(1);
  const [receiptPhoto, setReceiptPhoto] = useState(null);
  const [stockWarnings, setStockWarnings] = useState([]);
  const [ackStockWarnings, setAckStockWarnings] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    customersAPI.list({ page_size: 100, is_active: true }).then((res) => {
      const rows = res.data?.results || res.data || [];
      setCustomerOptions(
        rows.map((c) => ({ value: String(c.id), label: c.name || c.customer_code || `#${c.id}` }))
      );
    });
    usersAPI.list({ page_size: 100 }).then((res) => {
      const rows = res.data?.results || res.data || [];
      setStaffOptions(
        rows.map((u) => ({
          value: String(u.id),
          label: [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username,
        }))
      );
    });
  }, []);

  useEffect(() => {
    const term = productSearch.trim();
    if (!term || selectedProduct) {
      setProductResults([]);
      return undefined;
    }
    const timer = setTimeout(async () => {
      setSearchingProducts(true);
      try {
        const res = await productsAPI.list({
          search: term,
          is_active: 'true',
          page_size: 20,
        });
        const rows = res.data?.results || res.data || [];
        setProductResults(Array.isArray(rows) ? rows : []);
      } catch {
        setProductResults([]);
        toast.error('Could not search products');
      } finally {
        setSearchingProducts(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [productSearch, selectedProduct]);

  useEffect(() => {
    setAckStockWarnings(false);
    if (!lines.length || !occurredAt) {
      setStockWarnings([]);
      return;
    }
    const timer = setTimeout(() => {
      salesAPI
        .backfillPreflight({
          occurred_at: toIsoDatetime(occurredAt),
          items: lines.map((row) => ({
            product_id: row.product_id,
            variant_id: row.variant_id ?? undefined,
            quantity: row.quantity,
            unit_price: row.unit_price,
          })),
        })
        .then((res) => setStockWarnings(res.data?.warnings || []))
        .catch(() => setStockWarnings([]));
    }, 400);
    return () => clearTimeout(timer);
  }, [occurredAt, lines]);

  const total = useMemo(
    () => lines.reduce((sum, row) => sum + row.quantity * row.unit_price, 0),
    [lines]
  );

  const addLineFromProduct = useCallback((product, variant, qty) => {
    const quantity = Math.max(1, parseInt(qty, 10) || 1);
    const unitPrice = variant
      ? parseFloat(variant.effective_price || variant.price || product.price || product.selling_price || 0)
      : parseFloat(product.price ?? product.selling_price ?? 0);
    const variantLabel = variant ? getVariantRowLabel(variant) : '';
    const productName = variantLabel
      ? `${product.name} — ${variantLabel}`
      : `${product.name}${product.sku ? ` (${product.sku})` : ''}`;

    setLines((prev) => [
      ...prev,
      {
        key: `${product.id}-${variant?.id || 'base'}-${Date.now()}`,
        product_id: product.id,
        variant_id: variant?.id ?? null,
        product_name: productName,
        quantity,
        unit_price: unitPrice,
      },
    ]);
    setSelectedProduct(null);
    setProductSearch('');
    setProductResults([]);
    setPickQty('1');
  }, []);

  const pickProduct = useCallback((product) => {
    setSelectedProduct(product);
    setProductSearch('');
    setProductResults([]);
  }, []);

  const addLine = useCallback(() => {
    if (!selectedProduct) {
      toast.error('Pick a product to add.');
      return;
    }
    const qty = Math.max(1, parseInt(pickQty, 10) || 1);
    if (shouldOpenVariantPicker(selectedProduct)) {
      setPendingQty(qty);
      setVariantPickerProduct(selectedProduct);
      return;
    }
    addLineFromProduct(selectedProduct, null, qty);
  }, [addLineFromProduct, pickQty, selectedProduct]);

  const handleVariantSelect = useCallback(
    (payload) => {
      if (!variantPickerProduct) return;
      addLineFromProduct(variantPickerProduct, payload?.variant ?? null, pendingQty);
      setVariantPickerProduct(null);
      setPendingQty(1);
    },
    [addLineFromProduct, pendingQty, variantPickerProduct]
  );

  const removeLine = (key) => {
    setLines((prev) => prev.filter((row) => row.key !== key));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!lines.length) {
      toast.error('Add at least one item.');
      return;
    }
    if (!backfillReason.trim() || backfillReason.trim().length < 10) {
      toast.error('Enter a reason (min 10 characters).');
      return;
    }
    if (stockWarnings.length > 0 && !ackStockWarnings) {
      toast.warning('Confirm the stock-count warning before recording this sale.');
      return;
    }
    const paid = parseFloat(amountPaid) || 0;
    if (!allowPartial && paid <= 0 && paymentMethod !== 'wallet') {
      toast.error('Enter amount paid or allow partial payment.');
      return;
    }
    if (allowPartial && !customerId) {
      toast.error('Select a customer for partial payment or balance on account.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        occurred_at: toIsoDatetime(occurredAt),
        backfill_reason: backfillReason.trim(),
        sale_type: saleType,
        served_by_id: servedById ? parseInt(servedById, 10) : currentUserId,
        customer_id: customerId ? parseInt(customerId, 10) : null,
        payment_method: paymentMethod,
        payment_reference: paymentReference,
        amount_paid: paid,
        allow_partial_payment: allowPartial,
        acknowledge_stock_warnings: ackStockWarnings,
        items: lines.map((row) => ({
          product_id: row.product_id,
          variant_id: row.variant_id ?? undefined,
          quantity: row.quantity,
          unit_price: row.unit_price,
        })),
      };
      if (saleType === 'normal') {
        payload.create_invoice = true;
      }

      const res = await salesAPI.backfill(payload, receiptPhoto);
      handleSaleBackfillResponse(res, {
        onApplied: (data) => {
          toast.success(`Past sale recorded as ${data.sale_number}`);
          navigate('/sales');
        },
        onPending: () => {
          toast.success(pendingApprovalToastMessage());
          navigate('/pending-approvals');
        },
      });
    } catch (error) {
      const data = error.response?.data;
      if (data?.stock_warnings?.length) {
        setStockWarnings(data.stock_warnings);
        toast.warning(data.error || 'Review stock warnings and confirm to continue.');
        return;
      }
      const msg =
        data?.error ||
        data?.occurred_at?.[0] ||
        data?.backfill_reason?.[0] ||
        data?.detail ||
        error.message;
      toast.error(typeof msg === 'string' ? msg : 'Could not record sale');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
    <form onSubmit={handleSubmit} className="space-y-6">
      {mcOn && mcBackfill ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          {backfillCopy.summary}
        </p>
      ) : null}

      <section className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="occurred_at">When did the sale happen?</Label>
          <Input
            id="occurred_at"
            type="datetime-local"
            value={occurredAt}
            min={minOccurredAtLocal(maxDays)}
            max={defaultOccurredAtLocal()}
            onChange={(e) => setOccurredAt(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <ChangeReasonField
            label={backfillCopy.label}
            placeholder={backfillCopy.placeholder}
            value={backfillReason}
            onChange={setBackfillReason}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label>Sale type</Label>
          <SearchableSelect
            value={saleType}
            onChange={selectValue(setSaleType)}
            options={[
              { value: 'pos', label: 'POS / walk-in' },
              { value: 'normal', label: 'Normal sale (invoice)' },
            ]}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Served by</Label>
          <SearchableSelect
            value={servedById}
            onChange={selectValue(setServedById)}
            placeholder="Who made the sale?"
            options={staffOptions}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Customer</Label>
          <SearchableSelect
            value={customerId}
            onChange={selectValue(setCustomerId)}
            placeholder="Walk-in (optional)"
            options={[{ value: '', label: 'None' }, ...customerOptions]}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="receipt_photo">Paper receipt photo (optional)</Label>
          <Input
            id="receipt_photo"
            type="file"
            accept="image/*"
            onChange={(e) => setReceiptPhoto(e.target.files?.[0] || null)}
          />
          <p className="text-xs text-muted-foreground">
            Admin only — not printed on customer receipts.
          </p>
        </div>
      </section>

      {stockWarnings.length > 0 ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-950">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            Stock was adjusted after this sale date
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {stockWarnings.map((w) => (
              <li key={w.product_id}>{w.message}</li>
            ))}
          </ul>
          <label className="mt-3 flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={ackStockWarnings}
              onChange={(e) => setAckStockWarnings(e.target.checked)}
            />
            <span>I understand current stock may not match what was on hand when this sale happened.</span>
          </label>
        </div>
      ) : null}

      <section className="space-y-3 overflow-visible rounded-lg border p-4">
        <h2 className="font-semibold">Items</h2>
        <div className="space-y-2">
          <Label>Product</Label>
          {selectedProduct ? (
            <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{selectedProduct.name}</span>
                {selectedProduct.sku ? (
                  <span className="text-muted-foreground"> ({selectedProduct.sku})</span>
                ) : null}
                {selectedProduct.has_variants ? (
                  <span className="text-muted-foreground"> · pick variant on Add</span>
                ) : null}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setSelectedProduct(null)}
              >
                <X className="mr-1 h-4 w-4" />
                Change
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && productResults[0]) {
                    e.preventDefault();
                    pickProduct(productResults[0]);
                  }
                }}
                placeholder="Type product name or SKU…"
                className="pl-9"
              />
              {productSearch.trim() ? (
                <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-md border bg-background shadow-md">
                  {searchingProducts ? (
                    <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>
                  ) : null}
                  {!searchingProducts && productResults.length === 0 ? (
                    <li className="px-3 py-2 text-sm text-muted-foreground">No products found</li>
                  ) : null}
                  {productResults.map((product) => (
                    <li key={product.id}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
                        onClick={() => pickProduct(product)}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block font-medium">{product.name}</span>
                          {product.sku ? (
                            <span className="text-xs text-muted-foreground">{product.sku}</span>
                          ) : null}
                        </span>
                        <span className="shrink-0 text-primary tabular-nums">
                          {formatCurrency(product.price ?? product.selling_price ?? 0)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="w-24 space-y-1">
            <Label>Qty</Label>
            <Input
              type="number"
              min={1}
              value={pickQty}
              onChange={(e) => setPickQty(e.target.value)}
            />
          </div>
          <Button type="button" variant="secondary" onClick={addLine} disabled={!selectedProduct}>
            <Plus className="mr-1 h-4 w-4" />
            Add
          </Button>
        </div>
        {lines.length === 0 ? (
          <p className="text-sm text-muted-foreground">No items yet.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {lines.map((row) => (
              <li key={row.key} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                <span>
                  {row.product_name} × {row.quantity} @ {formatCurrency(row.unit_price)}
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-medium tabular-nums">
                    {formatCurrency(row.quantity * row.unit_price)}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeLine(row.key)}
                    aria-label="Remove line"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="text-right font-semibold">Total: {formatCurrency(total)}</p>
      </section>

      <section className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Payment method</Label>
          <SearchableSelect
            value={paymentMethod}
            onChange={selectValue(setPaymentMethod)}
            options={[
              { value: 'cash', label: 'Cash' },
              { value: 'mpesa', label: 'M-Pesa' },
              { value: 'card', label: 'Card' },
              { value: 'other', label: 'Other' },
            ]}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Payment reference</Label>
          <Input
            value={paymentReference}
            onChange={(e) => setPaymentReference(e.target.value)}
            placeholder="M-Pesa code, etc."
          />
        </div>
        <div className="space-y-1.5">
          <Label>Amount paid</Label>
          <Input
            type="number"
            min={0}
            step="0.01"
            value={amountPaid}
            onChange={(e) => setAmountPaid(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            checked={allowPartial}
            onChange={(e) => setAllowPartial(e.target.checked)}
          />
          Allow partial payment / balance on customer account
        </label>
      </section>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" asChild>
          <Link to="/sales">Cancel</Link>
        </Button>
        <Button type="submit" disabled={submitting}>
          <Clock className="mr-1 h-4 w-4" />
          {mcOn && mcBackfill ? 'Submit for approval' : 'Record sale'}
        </Button>
      </div>
    </form>

      {variantPickerProduct ? (
        <VariantSelector
          product={variantPickerProduct}
          validateStock={false}
          onSelect={handleVariantSelect}
          onClose={() => setVariantPickerProduct(null)}
        />
      ) : null}
    </>
  );
}

function BulkPastSaleImport({ mcOn, mcBackfill }) {
  const navigate = useNavigate();
  const [csvFile, setCsvFile] = useState(null);
  const [ackStockWarnings, setAckStockWarnings] = useState(false);
  const [importing, setImporting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const downloadTemplate = async () => {
    try {
      const res = await salesAPI.backfillImportTemplate();
      downloadBlob(res.data, 'past_sales_import_template.csv');
    } catch {
      toast.error('Could not download template');
    }
  };

  const handleImport = async (e) => {
    e.preventDefault();
    if (!csvFile) {
      toast.error('Choose a CSV file.');
      return;
    }
    setImporting(true);
    try {
      const res = await salesAPI.backfillImportCsv(csvFile, {
        acknowledge_stock_warnings: ackStockWarnings,
      });
      setLastResult(res.data);
      toast.success(res.data?.message || 'Import finished');
      if (res.data?.pending > 0) {
        navigate('/pending-approvals');
      } else if (res.data?.created > 0) {
        navigate('/sales');
      }
    } catch (error) {
      const data = error.response?.data;
      toast.error(data?.error || data?.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  return (
    <form onSubmit={handleImport} className="space-y-6">
      {mcOn && mcBackfill ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          Each imported sale may require checker approval before stock and accounts update.
        </p>
      ) : null}

      <section className="space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-semibold">Bulk CSV import</h2>
            <p className="text-sm text-muted-foreground">
              One row per line item. Use the same sale_reference to group items into one sale.
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={downloadTemplate}>
            <Download className="mr-1 h-4 w-4" />
            Download template
          </Button>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="csv_file">CSV file</Label>
          <Input
            id="csv_file"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
          />
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={ackStockWarnings}
            onChange={(e) => setAckStockWarnings(e.target.checked)}
          />
          <span>
            Acknowledge stock-count warnings when stock was adjusted after a sale date in the file.
          </span>
        </label>
      </section>

      {lastResult?.errors?.length ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm">
          <p className="font-medium">Issues</p>
          <ul className="mt-1 list-disc pl-5">
            {lastResult.errors.slice(0, 10).map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" asChild>
          <Link to="/sales">Cancel</Link>
        </Button>
        <Button type="submit" disabled={importing || !csvFile}>
          <Upload className="mr-1 h-4 w-4" />
          Import sales
        </Button>
      </div>
    </form>
  );
}

export default function RecordPastSale() {
  const { settings } = useStoreSettings();
  const backfillCopy = makerCheckerReasonCopy('sale_backfill');
  const mcOn = isMakerCheckerEnabled(settings);
  const mcBackfill = settings.backfill_maker_checker_enabled !== false;
  const maxDays = Math.max(1, parseInt(settings.backfill_max_days, 10) || 30);

  return (
    <PageShell>
      <PageHeader
        title="Record past sale"
        description={`Enter sales that happened outside the system (up to ${maxDays} days ago). Stock, accounts, and reports update like a normal sale.`}
      >
        <Button variant="outline" asChild>
          <Link to="/sales">Back to sales</Link>
        </Button>
      </PageHeader>

      <div className="mx-auto max-w-3xl">
        <Tabs defaultValue="single">
          <TabsList className="mb-4 grid w-full grid-cols-2">
            <TabsTrigger value="single">Single sale</TabsTrigger>
            <TabsTrigger value="bulk">Bulk CSV</TabsTrigger>
          </TabsList>
          <TabsContent value="single">
            <SinglePastSaleForm
              maxDays={maxDays}
              mcOn={mcOn}
              mcBackfill={mcBackfill}
              backfillCopy={backfillCopy}
            />
          </TabsContent>
          <TabsContent value="bulk">
            <BulkPastSaleImport mcOn={mcOn} mcBackfill={mcBackfill} />
          </TabsContent>
        </Tabs>
      </div>
    </PageShell>
  );
}
