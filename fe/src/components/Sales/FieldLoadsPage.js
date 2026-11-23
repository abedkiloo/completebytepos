import React, { useCallback, useEffect, useState } from 'react';

import { customersAPI, fieldLoadsAPI, productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { displayStatus, loadMatchesFilter, missingUnits, saleBasketTotal, shortageUnits, statusLabel } from '../../utils/fieldLoad';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { PageHeader, PageShell } from '../page';
import { isFeatureEnabled } from '../../utils/moduleSettings';

const FILTERS = [
  { id: 'all', label: 'All', empty: 'No field loads yet.' },
  { id: 'open', label: 'Open', empty: 'No loads are out for sale.' },
  { id: 'awaiting', label: 'Awaiting approval', empty: 'Nothing is waiting for approval.' },
  { id: 'shortage', label: 'Shortage', empty: 'No shortages to review.' },
  { id: 'accepted', label: 'Accepted', empty: 'No accepted loads.' },
];

/**
 * Field loads for the shop and the agent.
 *
 * Issuing stock, the physical count, and the manager's decision live here.
 * A sale on this screen is a field-load sale: it uses stock already on the
 * load and does not create a field order.
 */
export default function FieldLoadsPage() {
  const loadsOn = isFeatureEnabled('sales', 'field_load');
  const [book, setBook] = useState({ can_issue: false, can_approve: false, results: [] });
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState('all');
  const [view, setView] = useState('list');
  const [loading, setLoading] = useState(true);

  /**
   * Reload the newest 100 loads this user may see.
   *
   * @returns {Promise<void>} Sets an error toast when the request fails.
   */
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await fieldLoadsAPI.list();
      setBook(data);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not open field loads.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loadsOn) load();
  }, [load, loadsOn]);

  const results = book.results || [];
  const visible = results.filter((row) => loadMatchesFilter(row, filter));
  const selected = results.find((row) => row.id === selectedId) || null;
  const activeFilter = FILTERS.find((item) => item.id === filter) || FILTERS[0];

  /**
   * Put an updated load at the top of the list.
   *
   * @param {object} next Serialized load with an `id`.
   * @returns {void}
   */
  const replace = (next) => {
    setBook((prev) => ({
      ...prev,
      results: [next, ...prev.results.filter((row) => row.id !== next.id)],
    }));
    setSelectedId(next.id);
  };

  /**
   * Open one tab and leave the approval or the create form.
   *
   * @param {string} nextFilter One of `FILTERS[].id`.
   * @returns {void}
   */
  const showList = (nextFilter) => {
    setFilter(nextFilter);
    setView('list');
  };

  if (!loadsOn) {
    return (
      <PageShell>
        <PageHeader
          eyebrow="Sales"
          title="Field operations"
          description="Field loads are turned off. Turn them on under Module settings, Sales, Field loads."
        />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow="Sales"
        title="Field operations"
        description="Sell from stock already on a load. The shop counts what comes back."
      />
      {view === 'list' && (
        <>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={filter === item.id}
                className={`rounded-full px-3 py-1 text-sm ${filter === item.id ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground'}`}
                onClick={() => showList(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {book.can_issue && (
            <Button type="button" variant="outline" onClick={() => setView('create')}>
              Create new field load
            </Button>
          )}
          {loading && <p className="text-sm text-muted-foreground">Opening loads…</p>}
          {!loading && visible.length === 0 && (
            <p className="text-sm text-muted-foreground">{activeFilter.empty}</p>
          )}
          <ul className="space-y-2">
            {visible.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-card px-3 py-3 text-left"
                  onClick={() => {
                    setSelectedId(row.id);
                    setView('detail');
                  }}
                >
                  <span>
                    <span className="block font-medium">{row.agent_name}</span>
                    <span className="text-sm text-muted-foreground">{row.reference || `Load ${row.id}`}</span>
                  </span>
                  <span className="text-right">
                    <StatusBadge status={displayStatus(row)} />
                    <span className="mt-1 block text-sm text-muted-foreground">
                      Expected {formatCurrency(row.money?.expected)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {view === 'create' && book.can_issue && (
        <IssueForm
          onBack={() => setView('list')}
          onCreated={(next) => {
            replace(next);
            showList(next?.status === 'open' ? 'open' : 'awaiting');
          }}
        />
      )}
      {view === 'detail' && selected && (
        <LoadDetail
          load={selected}
          canApprove={book.can_approve}
          onChange={replace}
          onBack={() => setView('list')}
        />
      )}
    </PageShell>
  );
}

/**
 * Colored status chip using the app tokens.
 *
 * @param {object} props.status Display status.
 */
function StatusBadge({ status }) {
  const tone = status === 'shortage'
    ? 'bg-warning/15 text-warning'
    : status === 'accepted'
      ? 'bg-primary/10 text-primary'
      : status === 'open'
        ? 'bg-success/15 text-success'
        : 'bg-secondary text-secondary-foreground';
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>{statusLabel(status)}</span>;
}

/**
 * A sales person writes a new load for themselves. A manager chooses
 * themselves or another person, and that load opens immediately.
 *
 * Product search uses the same lookup as the till: name, SKU, or barcode,
 * and the matches update as the text settles. Choosing a product closes
 * the list and shows the quantity in that same place. The reference is
 * assigned when the load is issued.
 *
 * @param {Function} props.onCreated Receives the created load.
 * @param {Function} props.onBack Returns to the load list.
 */
function IssueForm({ onCreated, onBack }) {
  const [agents, setAgents] = useState([]);
  const [agentId, setAgentId] = useState('');
  const [chooseEmployee, setChooseEmployee] = useState(false);
  const [carrierReady, setCarrierReady] = useState(false);
  const [lockedName, setLockedName] = useState('');
  const [query, setQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [searching, setSearching] = useState(false);
  const [picked, setPicked] = useState(null);
  const [takeQty, setTakeQty] = useState('1');
  const [lines, setLines] = useState([]);
  const [saving, setSaving] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 280);

  useEffect(() => {
    fieldLoadsAPI.agents().then(({ data }) => {
      const rows = Array.isArray(data.results) ? data.results : [];
      setAgents(rows);
      const choose = data.choose_employee !== false;
      setChooseEmployee(choose);
      if (!choose && rows[0]) {
        setAgentId(String(rows[0].id));
        setLockedName(rows[0].name || '');
      }
      setCarrierReady(true);
    }).catch(() => {
      setAgents([]);
      setCarrierReady(true);
    });
  }, []);

  useEffect(() => {
    const term = debouncedQuery.trim();
    if (!term) {
      setProducts([]);
      setSearching(false);
      return undefined;
    }
    let cancelled = false;
    setSearching(true);
    productsAPI.search(term, 20).then(({ data }) => {
      if (cancelled) return;
      const rows = Array.isArray(data) ? data : (data.results || []);
      setProducts(rows.slice(0, 20));
    }).catch(() => {
      if (!cancelled) setProducts([]);
    }).finally(() => {
      if (!cancelled) setSearching(false);
    });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  /**
   * Put the selected product on the draft, or add to its quantity.
   *
   * Quantity is a whole number from 1 to the available stock, and at most
   * 100000. A product already on the draft keeps one row.
   *
   * @returns {void}
   */
  const addPicked = () => {
    if (!picked) return;
    const stock = Number(picked.stock_quantity);
    const available = Number.isFinite(stock) && stock > 0 ? Math.min(stock, 100000) : 100000;
    const asked = Math.min(available, Math.max(1, Math.floor(Number(takeQty) || 1)));
    setLines((prev) => {
      const existing = prev.find((line) => line.product_id === picked.id);
      if (!existing) {
        return [...prev, {
          product_id: picked.id,
          name: picked.name,
          quantity: String(asked),
          stock: available,
        }];
      }
      const next = Math.min(available, (Number(existing.quantity) || 0) + asked);
      return prev.map((line) => (
        line.product_id === picked.id ? { ...line, quantity: String(next) } : line
      ));
    });
    setTakeQty('1');
    setPicked(null);
    setQuery('');
    setProducts([]);
  };

  /**
   * Drop one draft line before the load is issued.
   *
   * @param {number} productId Product id on the draft, a positive integer.
   * @returns {void} Shop stock is unchanged.
   */
  const removeLine = (productId) => {
    setLines((prev) => prev.filter((line) => line.product_id !== productId));
  };

  /**
   * Issue the chosen lines.
   *
   * @returns {Promise<void>}
   */
  const save = async () => {
    setSaving(true);
    try {
      const { data } = await fieldLoadsAPI.create({
        agent_id: Number(agentId),
        lines: lines.map((line) => ({ product_id: line.product_id, quantity: Number(line.quantity) })),
      });
      toast.success(chooseEmployee
        ? 'Load issued. These pieces have left the shop.'
        : 'Load sent to the manager. Shop stock has not moved yet.');
      setLines([]);
      setPicked(null);
      setQuery('');
      onCreated(data);
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not issue this load.');
    } finally {
      setSaving(false);
    }
  };

  const totalQty = lines.reduce((sum, line) => sum + (Number(line.quantity) || 0), 0);
  const pickedStock = Number(picked?.stock_quantity);

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-4">
      <Button type="button" variant="ghost" onClick={onBack}>Back to loads</Button>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Create new field load</h2>
        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Draft</span>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Load reference</p>
        <p className="text-sm font-medium">Assigned when the load is issued</p>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-muted-foreground">
          {chooseEmployee ? 'Person carrying this load' : 'Sales employee'}
        </span>
        {!carrierReady ? (
          <Input aria-label="Sales employee" value="" readOnly />
        ) : chooseEmployee ? (
          <>
            <select
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Person carrying this load"
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
            >
              <option value="">Choose</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              Choose yourself or another person. This load is ready to sell and does not wait for approval.
            </p>
          </>
        ) : (
          <Input aria-label="Sales employee" value={lockedName} readOnly />
        )}
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-muted-foreground">Load date</span>
        <Input aria-label="Load date" value={formatDate(new Date())} readOnly />
      </label>

      <div className="space-y-3 border-t border-border pt-3">
        <h3 className="text-sm font-semibold">Add products to load</h3>
        <Input
          aria-label="Find product"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPicked(null);
          }}
          placeholder="Type a name, then choose the product"
        />
        {searching && !picked && <p className="text-xs text-muted-foreground">Searching…</p>}
        {!picked && !searching && debouncedQuery.trim() && products.length === 0 && (
          <p className="text-xs text-muted-foreground">No matching product.</p>
        )}
        {!picked && products.length > 0 && (
          <ul className="max-h-48 space-y-1 overflow-auto rounded-md border border-border p-1">
            {products.map((product) => (
              <li key={product.id}>
                <button
                  type="button"
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                  onClick={() => {
                    setPicked(product);
                    setTakeQty('1');
                    setQuery('');
                    setProducts([]);
                  }}
                >
                  <span className="block font-medium">{product.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {product.sku ? `SKU: ${product.sku} · ` : ''}Available: {product.stock_quantity ?? 0}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {picked && (
          <div className="space-y-3 rounded-md border border-primary p-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-base font-semibold">{picked.name}</p>
                <p className="text-xs text-muted-foreground">
                  {picked.sku ? `SKU: ${picked.sku} · ` : ''}Available: {picked.stock_quantity ?? 0} pieces
                </p>
              </div>
              {pickedStock > 0 && (
                <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success">In stock</span>
              )}
            </div>
            <label className="flex items-center justify-between gap-2">
              <span className="font-medium">How many to take</span>
              <Input
                type="number"
                min={1}
                max={pickedStock > 0 ? pickedStock : 100000}
                className="h-11 w-24 text-base"
                aria-label={`Quantity of ${picked.name}`}
                value={takeQty}
                onChange={(event) => setTakeQty(event.target.value)}
              />
            </label>
            <Button type="button" className="w-full" onClick={addPicked}>
              Add to load
            </Button>
            <Button type="button" variant="ghost" className="w-full" onClick={() => setPicked(null)}>
              Choose a different product
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-border pt-3">
        <h3 className="text-sm font-semibold">Current load items</h3>
        {lines.length === 0 && (
          <p className="text-sm text-muted-foreground">No products on this draft yet.</p>
        )}
        {lines.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 font-medium">Product</th>
                <th className="py-1 text-right font-medium">Quantity</th>
                <th className="py-1 text-right font-medium"> </th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, index) => (
                <tr key={line.product_id} className="border-t border-border">
                  <td className="py-2">{line.name}</td>
                  <td className="py-2 text-right">
                    <Input
                      type="number"
                      min={1}
                      className="ml-auto h-8 w-20"
                      aria-label={`Quantity of ${line.name}`}
                      value={line.quantity}
                      onChange={(event) => {
                        const quantity = event.target.value;
                        setLines((prev) => prev.map((row, rowIndex) => (
                          rowIndex === index ? { ...row, quantity } : row
                        )));
                      }}
                    />
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-destructive"
                      aria-label={`Remove ${line.name}`}
                      onClick={() => removeLine(line.product_id)}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div>
          <p className="text-sm font-semibold">Total product quantities</p>
          <p className="text-lg font-semibold tabular-nums">{totalQty}</p>
        </div>
      </div>
      <div className="rounded-xl bg-success/10 p-3 text-sm">
        <p className="font-medium text-success">Stock movement confirmation</p>
        <p>
          {chooseEmployee
            ? 'Shop stock leaves as soon as you issue this load. No second approval.'
            : 'A manager confirms these quantities. Shop stock leaves only after that approval.'}
        </p>
      </div>
      <Button type="button" variant="success" className="w-full" onClick={save} disabled={saving || !agentId || lines.length === 0}>
        {saving ? 'Sending…' : (chooseEmployee ? 'Issue load' : 'Submit for approval')}
      </Button>
    </section>
  );
}

/**
 * A sent-back load, for the person who wrote it to correct and send again.
 *
 * Someone else sees the products and the manager's note, and cannot change them.
 * Quantity on each row is a whole number from 1 to 100000. Shop stock does not move.
 *
 * @param {object} props.load Serialized load in `issue_rejected`.
 * @param {Function} props.onChange Receives the load after it is sent again.
 * @param {Function} props.onBack Returns to the load list after a successful send.
 * @returns {JSX.Element}
 */
function ReviseSentLoad({ load, onChange, onBack }) {
  const [lines, setLines] = useState(() => (load.lines || []).map((item) => ({
    product_id: item.product_id,
    name: item.product_name,
    quantity: String(item.quantity_taken),
  })));
  const [query, setQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [picked, setPicked] = useState(null);
  const [takeQty, setTakeQty] = useState('1');
  const [saving, setSaving] = useState(false);
  const debouncedQuery = useDebouncedValue(query, 280);
  const canRevise = Boolean(load.can_revise_issue);

  useEffect(() => {
    if (!canRevise) return undefined;
    const term = debouncedQuery.trim();
    if (!term) {
      setProducts([]);
      return undefined;
    }
    let cancelled = false;
    productsAPI.search(term, 20).then(({ data }) => {
      if (cancelled) return;
      const rows = Array.isArray(data) ? data : (data.results || []);
      setProducts(rows.slice(0, 20));
    }).catch(() => {
      if (!cancelled) setProducts([]);
    });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, canRevise]);

  /**
   * Add the chosen product, or increase the quantity already on the load.
   *
   * @returns {void} Does nothing until a product is chosen.
   */
  const addPicked = () => {
    if (!picked) return;
    const stock = Number(picked.stock_quantity);
    const available = Number.isFinite(stock) && stock > 0 ? Math.min(stock, 100000) : 100000;
    const asked = Math.min(available, Math.max(1, Math.floor(Number(takeQty) || 1)));
    setLines((prev) => {
      const existing = prev.find((line) => line.product_id === picked.id);
      if (!existing) {
        return [...prev, { product_id: picked.id, name: picked.name, quantity: String(asked) }];
      }
      const next = Math.min(available, (Number(existing.quantity) || 0) + asked);
      return prev.map((line) => (
        line.product_id === picked.id ? { ...line, quantity: String(next) } : line
      ));
    });
    setPicked(null);
    setQuery('');
    setProducts([]);
    setTakeQty('1');
  };

  /**
   * Send the corrected products back to the manager.
   *
   * @returns {Promise<void>} Shop stock stays put.
   */
  const sendAgain = async () => {
    setSaving(true);
    try {
      const { data } = await fieldLoadsAPI.reviseIssue(load.id, {
        lines: lines.map((line) => ({ product_id: line.product_id, quantity: Number(line.quantity) })),
      });
      toast.success('Sent again for approval. Shop stock has not moved.');
      onChange(data);
      onBack();
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not send this load again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3 rounded-xl border border-border p-3">
      <h3 className="text-base font-semibold">This load was sent back</h3>
      <p className="text-sm text-muted-foreground">
        {load.review_note
          ? load.review_note
          : 'A manager asked for these quantities to be checked.'}
      </p>
      {canRevise ? (
        <>
          <p className="text-sm">Change the products, then send the same load for approval again.</p>
          <ul className="space-y-2">
            {lines.map((line) => (
              <li key={line.product_id} className="flex items-center gap-2">
                <span className="min-w-0 flex-1 text-sm font-medium">{line.name}</span>
                <Input
                  aria-label={`Quantity of ${line.name}`}
                  type="number"
                  min={1}
                  max={100000}
                  className="w-24"
                  value={line.quantity}
                  onChange={(event) => setLines((prev) => prev.map((row) => (
                    row.product_id === line.product_id ? { ...row, quantity: event.target.value } : row
                  )))}
                />
                <Button
                  type="button"
                  variant="ghost"
                  aria-label={`Remove ${line.name}`}
                  onClick={() => setLines((prev) => prev.filter((row) => row.product_id !== line.product_id))}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
          {lines.length === 0 && (
            <p className="text-sm text-muted-foreground">Add at least one product.</p>
          )}
          {!picked && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Add a product</span>
              <Input
                aria-label="Find product"
                value={query}
                placeholder="Type a name, then choose the product"
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPicked(null);
                }}
              />
            </label>
          )}
          {!picked && products.length > 0 && (
            <ul className="space-y-1">
              {products.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    className="w-full rounded-lg border border-border px-3 py-2 text-left text-sm"
                    onClick={() => {
                      setPicked(product);
                      setQuery('');
                      setProducts([]);
                      setTakeQty('1');
                    }}
                  >
                    {product.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {picked && (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <p className="font-medium">{picked.name}</p>
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">How many to take</span>
                <Input
                  aria-label={`Quantity of ${picked.name}`}
                  type="number"
                  min={1}
                  value={takeQty}
                  onChange={(event) => setTakeQty(event.target.value)}
                />
              </label>
              <Button type="button" variant="success" onClick={addPicked}>Add to load</Button>
            </div>
          )}
          <Button
            type="button"
            variant="success"
            className="w-full"
            disabled={saving || lines.length === 0}
            onClick={sendAgain}
          >
            {saving ? 'Sending…' : 'Send again for approval'}
          </Button>
        </>
      ) : (
        <ul className="space-y-1 text-sm">
          {load.lines.map((item) => (
            <li key={item.id} className="flex justify-between gap-2">
              <span>{item.product_name}</span>
              <span>{item.quantity_taken}</span>
            </li>
          ))}
          <li className="text-muted-foreground">The person who wrote this load can change it and send it again.</li>
        </ul>
      )}
    </div>
  );
}

/**
 * One load: the products on the left, the sale on the right.
 *
 * Each product that is still on the load has its own quantity. Blank means
 * that product is not in this sale. One payment covers every quantity and
 * stays beside the list on a wide screen. A narrow screen puts that short
 * sale panel on top of the products. The return count is a separate step.
 *
 * @param {object} props.load Serialized load.
 * @param {boolean} props.canApprove Whether this user may accept the count.
 * @param {Function} props.onChange Receives the updated load.
 * @param {Function} props.onBack Returns to the load list. A finished approval uses this too.
 */
function LoadDetail({ load, canApprove, onChange, onBack }) {
  const [returns, setReturns] = useState({});
  const [saleQtys, setSaleQtys] = useState({});
  const [paid, setPaid] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [customers, setCustomers] = useState([]);
  const [counting, setCounting] = useState(false);
  const [payment, setPayment] = useState('cash');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const shown = displayStatus(load);
  const short = shortageUnits(load.lines);

  useEffect(() => {
    const next = {};
    load.lines.forEach((line) => {
      next[line.id] = line.quantity_returned ?? '';
    });
    setReturns(next);
    setSaleQtys({});
    setCounting(false);
  }, [load]);

  useEffect(() => {
    if (load.status !== 'open') return undefined;
    customersAPI.list({ page_size: 50, is_active: 'true' }).then(({ data }) => {
      setCustomers(data.results || []);
    }).catch(() => setCustomers([]));
    return undefined;
  }, [load.status]);

  const saleRows = load.lines.map((item) => {
    const available = item.available ?? (Number(item.quantity_taken) - Number(item.quantity_sold || 0));
    const typed = Number(saleQtys[item.id]);
    const quantity = Number.isFinite(typed) && typed > 0 ? Math.min(Math.floor(typed), available) : 0;
    return { item, available, quantity };
  });
  const chosen = saleRows.filter((row) => row.quantity > 0);
  const total = saleBasketTotal(chosen.map((row) => ({
    unitPrice: row.item.unit_price,
    quantity: row.quantity,
  })));
  const taken = load.units_taken ?? load.lines.reduce((sum, item) => sum + Number(item.quantity_taken || 0), 0);
  const sold = load.units_sold ?? load.lines.reduce((sum, item) => sum + Number(item.quantity_sold || 0), 0);

  /**
   * Set how many of one product go on this sale.
   *
   * @param {number|string} lineId Load line id.
   * @param {number} next Whole units, 0 through what is still available.
   *   Zero clears the field.
   * @returns {void}
   */
  const setLineQty = (lineId, next) => {
    setSaleQtys((prev) => ({
      ...prev,
      [lineId]: next > 0 ? String(next) : '',
    }));
  };

  /**
   * Run one load action and replace the open load with the response.
   *
   * @param {Function} work Returns the API promise.
   * @param {string} success Toast text, one short sentence.
   * @param {boolean} [leave] Return to the list after a successful approval.
   * @returns {Promise<void>}
   */
  const run = async (work, success, leave = false) => {
    setBusy(true);
    try {
      const { data } = await work();
      toast.success(success);
      onChange(data);
      if (leave) onBack();
    } catch (error) {
      toast.error(error?.response?.data?.error || 'Could not update this load.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-4" data-testid="field-load-detail">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Button type="button" variant="ghost" className="-ml-2 h-8 px-2" onClick={onBack}>
            Back to loads
          </Button>
          <h2 className="truncate text-lg font-semibold">{load.reference || `Load ${load.id}`}</h2>
          <p className="text-sm text-muted-foreground">
            {load.agent_name}
            {load.issued_at ? ` · ${formatDate(load.issued_at)}` : ''}
            {` · Taken ${taken} · Sold ${sold}`}
          </p>
        </div>
        <StatusBadge status={shown} />
      </div>

      {load.status === 'awaiting_issue' && (
        <div className="space-y-3 rounded-xl border border-border p-3">
          <h3 className="text-base font-semibold">Quantities to approve</h3>
          <p className="text-sm text-muted-foreground">
            {load.issued_by ? `${load.issued_by} wrote this load. ` : ''}
            Shop stock stays on the shelf until a manager approves it.
          </p>
          <ul className="space-y-1 text-sm">
            {load.lines.map((item) => (
              <li key={item.id} className="flex justify-between gap-2">
                <span>{item.product_name}</span>
                <span>{item.quantity_taken}</span>
              </li>
            ))}
          </ul>
          {load.can_confirm_issue && (
            <div className="space-y-2">
              <Button
                type="button"
                variant="success"
                disabled={busy}
                onClick={() => run(
                  () => fieldLoadsAPI.approveIssue(load.id),
                  'Load approved. Those quantities have left the shop.',
                  true,
                )}
              >
                Approve quantities
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => run(
                  () => fieldLoadsAPI.declineIssue(load.id, { note: 'Check the quantities' }),
                  'Sent back to the sales person.',
                  true,
                )}
              >
                Send back
              </Button>
            </div>
          )}
          {!load.can_confirm_issue && (
            <p className="text-sm">Waiting for a manager. Selling starts after this load is approved. It will then be under Open.</p>
          )}
        </div>
      )}

      {load.status === 'open' && !counting && (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="order-2 space-y-2 lg:order-1">
            <h3 className="text-sm font-semibold">Sell from this load</h3>
            <p className="text-sm text-muted-foreground">
              Enter a quantity for every product in this sale. Leave the others blank. These pieces are already on the load.
            </p>
            {saleRows.map((row) => (
              <div
                key={row.item.id}
                className={`flex items-center gap-3 rounded-lg border bg-card px-3 py-2 ${row.quantity > 0 ? 'border-primary' : 'border-border'}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{row.item.product_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {row.available} left
                    {row.item.unit_price ? ` · ${formatCurrency(row.item.unit_price)}` : ''}
                  </p>
                </div>
                {row.available > 0 ? (
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-9 w-9 px-0"
                      aria-label={`Less ${row.item.product_name}`}
                      onClick={() => setLineQty(row.item.id, row.quantity - 1)}
                    >
                      −
                    </Button>
                    <Input
                      aria-label={`Quantity of ${row.item.product_name}`}
                      className="h-9 w-14 px-1 text-center"
                      inputMode="numeric"
                      value={saleQtys[row.item.id] ?? ''}
                      onChange={(event) => setSaleQtys((prev) => ({
                        ...prev,
                        [row.item.id]: event.target.value,
                      }))}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-9 w-9 px-0"
                      aria-label={`More ${row.item.product_name}`}
                      disabled={row.quantity >= row.available}
                      onClick={() => setLineQty(row.item.id, row.quantity + 1)}
                    >
                      +
                    </Button>
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground">Sold out</span>
                )}
              </div>
            ))}
            <Button type="button" variant="ghost" className="h-8 px-2" onClick={() => setCounting(true)}>
              Return to shop
            </Button>
          </div>
        <div className="order-1 space-y-3 rounded-lg border border-border bg-card p-3 lg:sticky lg:top-4 lg:order-2">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-xs text-muted-foreground">Sale total</p>
              <p className="text-2xl font-semibold tabular-nums">{formatCurrency(total)}</p>
            </div>
            <p className="text-right text-xs text-muted-foreground">
              {chosen.length === 0 ? 'No products yet' : `${chosen.length} in this sale`}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            This does not create a field order and it does not take the units off the shelf again.
          </p>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Customer</span>
            <select
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Customer"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
            >
              <option value="">Walk-in, fully paid</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>{customer.name}</option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-3 gap-1" role="radiogroup" aria-label="Payment">
            {[
              ['cash', 'Cash'],
              ['mpesa', 'M-Pesa'],
              ['credit', 'Credit'],
            ].map(([value, label]) => (
              <label
                key={value}
                className={`flex h-9 cursor-pointer items-center justify-center rounded-md text-sm ${payment === value ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground'}`}
              >
                <input
                  type="radio"
                  className="sr-only"
                  name="field-load-payment"
                  value={value}
                  checked={payment === value}
                  onChange={() => setPayment(value)}
                />
                {label}
              </label>
            ))}
          </div>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Amount received</span>
            <Input
              aria-label="Amount received"
              value={payment === 'credit' ? '0' : paid}
              disabled={payment === 'credit'}
              onChange={(event) => setPaid(event.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Note</span>
            <Input aria-label="Sale notes" value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
          </label>
          <Button
            type="button"
            variant="success"
            disabled={busy || chosen.length === 0}
            onClick={() => run(
              () => fieldLoadsAPI.sell(load.id, {
                lines: chosen.map((row) => ({
                  product_id: row.item.product_id,
                  ...(row.item.variant_id ? { variant_id: row.item.variant_id } : {}),
                  quantity: row.quantity,
                })),
                customer_id: customerId ? Number(customerId) : null,
                amount_paid: payment === 'credit' ? 0 : (paid || 0),
                payment_method: payment,
                client_channel: 'web',
                notes: note,
              }),
              'Field load sale recorded. Shop stock was not taken again.',
            )}
          >
            Record a field load sale
          </Button>
        </div>
        </div>
      )}

      {load.status === 'open' && counting && (
        <div className="space-y-3">
          <Button type="button" variant="ghost" onClick={() => setCounting(false)}>
            Back to stock
          </Button>
          <h3 className="text-base font-semibold">Physical stock count</h3>
          <p className="text-sm text-muted-foreground">
            Count the whole bag. Missing = taken − sold − returned, for each product.
          </p>
          {load.lines.map((item) => {
            const missing = missingUnits(item.quantity_taken, item.quantity_sold, returns[item.id]);
            return (
              <label key={item.id} className="block text-sm">
                <span className="mb-1 flex justify-between gap-2">
                  <span>{item.product_name}</span>
                  <span className="text-muted-foreground">
                    Taken {item.quantity_taken} · Sold {item.quantity_sold}
                    {missing == null ? '' : ` · Missing ${missing}`}
                  </span>
                </span>
                <Input
                  type="number"
                  min={0}
                  aria-label={`Returned ${item.product_name}`}
                  value={returns[item.id] ?? ''}
                  onChange={(event) => setReturns((prev) => ({ ...prev, [item.id]: event.target.value }))}
                />
              </label>
            );
          })}
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => run(
              () => fieldLoadsAPI.returnCount(load.id, {
                lines: load.lines.map((item) => ({
                  line_id: item.id,
                  quantity_returned: Number(returns[item.id] || 0),
                })),
              }),
              'Physical count sent to the manager.',
            )}
          >
            Submit physical count
          </Button>
        </div>
      )}

      {load.status === 'issue_rejected' && (
        <ReviseSentLoad load={load} onChange={onChange} onBack={onBack} />
      )}

      {load.status !== 'open' && load.status !== 'awaiting_issue' && load.status !== 'issue_rejected' && (
        <div className="space-y-3">
          <h3 className="text-base font-semibold">Stock accountability</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 font-medium">Product</th>
                <th className="py-1 font-medium">Taken</th>
                <th className="py-1 font-medium">Sold</th>
                <th className="py-1 font-medium">Returned</th>
                <th className="py-1 font-medium">Missing</th>
              </tr>
            </thead>
            <tbody>
              {load.lines.map((item) => (
                <tr key={item.id} className="border-t border-border">
                  <td className="py-1">{item.product_name}</td>
                  <td>{item.quantity_taken}</td>
                  <td>{item.quantity_sold}</td>
                  <td>{item.quantity_returned ?? '—'}</td>
                  <td>{item.quantity_missing ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 className="text-base font-semibold">Sales on this load</h3>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between"><dt>Expected sales value</dt><dd>{formatCurrency(load.money?.expected)}</dd></div>
            <div className="flex justify-between"><dt>Cash received</dt><dd>{formatCurrency(load.money?.cash)}</dd></div>
            <div className="flex justify-between"><dt>M-Pesa received</dt><dd>{formatCurrency(load.money?.mpesa)}</dd></div>
            <div className="flex justify-between"><dt>Customer credit</dt><dd>{formatCurrency(load.money?.credit)}</dd></div>
          </dl>
          {short > 0 && (
            <div className="rounded-xl bg-warning/15 p-3 text-sm">
              <p className="font-medium text-warning">Shortage identified</p>
              <p className="text-lg font-semibold text-warning">{short} units</p>
              <p>The manager can accept the shortage, or send the count back.</p>
            </div>
          )}
        </div>
      )}

      {load.status === 'pending_review' && canApprove && (
        <div className="space-y-2">
          <Button
            type="button"
            variant="success"
            disabled={busy}
            onClick={() => run(() => fieldLoadsAPI.accept(load.id, {}), 'Load accepted. Returns are back on the shelf.', true)}
          >
            Approve reconciliation
          </Button>
          <Button
            type="button"
            variant="outline"
            className="text-destructive"
            disabled={busy}
            onClick={() => run(() => fieldLoadsAPI.reject(load.id, { note: 'Count again' }), 'Sent back to be counted again.', true)}
          >
            Send back for correction
          </Button>
        </div>
      )}
    </section>
  );
}
