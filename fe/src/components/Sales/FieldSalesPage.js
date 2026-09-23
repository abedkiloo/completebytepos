import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MapPin, PackageCheck, Plus, RefreshCw } from 'lucide-react';
import { dispatchAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import {
  assignCommitRows,
  assignDriverError,
  canAssignDriver,
  canMarkReady,
  fieldOrderLineSummary,
  fieldOrderTotal,
  packCommitRows,
  packReadyError,
} from '../../utils/fieldSalesCommit';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import CommitConfirm from '../Shared/CommitConfirm';
import AddDriverDialog from './AddDriverDialog';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  FilterField,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  StatusBadge,
  ListPaginationRail,
} from '../page';

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'awaiting_pack', label: 'Awaiting pack' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'packing', label: 'Packing' },
  { value: 'ready', label: 'Ready for pickup' },
  { value: 'dispatched', label: 'Dispatched / delivered' },
  { value: 'out_for_delivery', label: 'Out for delivery' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'draft', label: 'Draft' },
];

const STATUS_LABELS = {
  draft: 'Draft',
  submitted: 'Submitted',
  packing: 'Packing',
  ready: 'Ready',
  out_for_delivery: 'Out for delivery',
  done: 'Done',
  cancelled: 'Cancelled',
};

const FieldSalesPage = () => {
  const { permissions } = getStoredAuth();
  const canPack = hasPermission(permissions, 'dispatch', 'update');
  const [orders, setOrders] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [packingId, setPackingId] = useState(null);
  const [assigningId, setAssigningId] = useState(null);
  const [selectedDriverId, setSelectedDriverId] = useState('');
  const [selected, setSelected] = useState(null);
  const [pending, setPending] = useState(null);
  const [showAddDriver, setShowAddDriver] = useState(false);
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    status: 'awaiting_pack',
    search: '',
  });
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    count: 0,
  });

  const loadDrivers = useCallback(async () => {
    if (!canPack) return;
    try {
      const response = await dispatchAPI.drivers();
      setDrivers(Array.isArray(response.data) ? response.data : []);
    } catch {
      setDrivers([]);
    }
  }, [canPack]);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        page: pagination.page,
        page_size: pagination.page_size,
      };
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.status) params.status = filters.status;
      if (filters.search.trim()) params.search = filters.search.trim();

      const response = await dispatchAPI.list(params);
      const data = response.data;
      if (data?.results) {
        setOrders(data.results);
        setPagination((prev) => ({ ...prev, count: data.count || 0 }));
      } else {
        const rows = Array.isArray(data) ? data : [];
        setOrders(rows);
        setPagination((prev) => ({ ...prev, count: rows.length }));
      }
    } catch (error) {
      setOrders([]);
      toast.error(
        error.response?.data?.detail
          || error.response?.data?.error
          || 'Failed to load field sales',
      );
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.page_size]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  useEffect(() => {
    loadDrivers();
  }, [loadDrivers]);

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const refreshSelected = async (orderId) => {
    if (selected?.id !== orderId) return;
    const refreshed = await dispatchAPI.get(orderId);
    setSelected(refreshed.data);
  };

  const executePack = async (order) => {
    setPackingId(order.id);
    try {
      await dispatchAPI.pack(order.id);
      toast.success(`Order #${order.id} marked ready for pickup`);
      await loadOrders();
      await refreshSelected(order.id);
    } catch (error) {
      const detail =
        error.response?.data?.status
        || error.response?.data?.detail
        || error.response?.data?.error
        || error.message;
      toast.error(typeof detail === 'string' ? detail : 'Could not mark ready');
    } finally {
      setPackingId(null);
    }
  };

  const executeAssign = async (order) => {
    setAssigningId(order.id);
    try {
      await dispatchAPI.assign(order.id, {
        delivery_agent_id: Number(selectedDriverId),
      });
      toast.success(`Order #${order.id} assigned to driver`);
      await loadOrders();
      await refreshSelected(order.id);
    } catch (error) {
      const detail =
        error.response?.data?.delivery_agent_id
        || error.response?.data?.status
        || error.response?.data?.detail
        || error.response?.data?.error
        || error.message;
      toast.error(
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail[0]
            : 'Could not assign driver',
      );
    } finally {
      setAssigningId(null);
    }
  };

  const requestPack = (order) => {
    const error = packReadyError(order, canPack);
    if (error) {
      toast.error(error);
      return;
    }
    setPending({ type: 'pack', order });
  };

  const requestAssign = (order) => {
    const error = assignDriverError(order, selectedDriverId, canPack);
    if (error) {
      toast.error(error);
      return;
    }
    setPending({ type: 'assign', order });
  };

  const confirmPending = async () => {
    const action = pending;
    if (!action) return;
    try {
      if (action.type === 'pack') {
        await executePack(action.order);
        return;
      }
      await executeAssign(action.order);
    } finally {
      setPending(null);
    }
  };

  const pendingDriver = drivers.find(
    (driver) => String(driver.id) === String(selectedDriverId),
  );
  const pendingRows = pending?.type === 'assign'
    ? assignCommitRows(pending.order, pendingDriver, formatCurrency)
    : pending
      ? packCommitRows(pending.order, formatCurrency)
      : [];

  const emptyMessage = useMemo(() => {
    if (filters.status === 'awaiting_pack') {
      return 'No visit orders waiting to be packed.';
    }
    return 'No field sales match these filters.';
  }, [filters.status]);

  if (loading && orders.length === 0) {
    return <PageLoading rows={8} />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Field sales"
        description="Visit orders from the field — pack, assign a delivery driver, or leave ready for drivers to claim."
      >
        <Button variant="outline" onClick={loadOrders} disabled={loading}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
        {canPack ? (
          <Button
            variant="outline"
            onClick={() => setShowAddDriver(true)}
            data-testid="field-sales-add-driver"
          >
            <Plus className="h-4 w-4" />
            Add driver
          </Button>
        ) : null}
      </PageHeader>

      <FilterBar>
        <FilterField label="From">
          <Input
            type="date"
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
            data-testid="field-sales-date-from"
          />
        </FilterField>
        <FilterField label="To">
          <Input
            type="date"
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
            data-testid="field-sales-date-to"
          />
        </FilterField>
        <FilterField label="Status">
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={filters.status}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            data-testid="field-sales-status"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField label="Customer / order">
          <Input
            placeholder="Name, phone, or order #"
            value={filters.search}
            onChange={(e) => handleFilterChange('search', e.target.value)}
          />
        </FilterField>
      </FilterBar>

      {orders.length === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No field sales"
          description={emptyMessage}
          actionLabel="Refresh"
          onAction={loadOrders}
        />
      ) : (
        <ListPaginationRail
          page={pagination.page}
          pageSize={pagination.page_size}
          totalCount={pagination.count}
          suffix={`${pagination.count} orders`}
          onPageChange={(page) => setPagination((prev) => ({ ...prev, page }))}
        >
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Order</DataTableHead>
              <DataTableHead>Customer</DataTableHead>
              <DataTableHead>Products</DataTableHead>
              <DataTableHead>Total</DataTableHead>
              <DataTableHead>Status</DataTableHead>
              <DataTableHead>Created</DataTableHead>
              <DataTableHead className="text-right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {orders.map((order) => (
                <DataTableRow key={order.id}>
                  <DataTableCell>
                    <button
                      type="button"
                      className="font-medium text-primary hover:underline"
                      onClick={() => setSelected(order)}
                    >
                      #{order.id}
                    </button>
                  </DataTableCell>
                  <DataTableCell>
                    <div className="font-medium">
                      {order.customer_name || '—'}
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {order.site_detail?.label
                        || (order.site_detail?.latitude
                          ? `${order.site_detail.latitude}, ${order.site_detail.longitude}`
                          : 'No pin')}
                    </div>
                  </DataTableCell>
                  <DataTableCell className="max-w-[220px] truncate text-sm">
                    {fieldOrderLineSummary(order)}
                  </DataTableCell>
                  <DataTableCell>{formatCurrency(fieldOrderTotal(order))}</DataTableCell>
                  <DataTableCell>
                    <StatusBadge
                      status={order.status}
                      label={STATUS_LABELS[order.status] || order.status}
                    />
                    {order.stock_allocated ? (
                      <div className="text-xs text-muted-foreground mt-1">Packed</div>
                    ) : null}
                  </DataTableCell>
                  <DataTableCell className="text-sm text-muted-foreground">
                    {formatDateTime(order.created_at)}
                  </DataTableCell>
                  <DataTableCell className="text-right space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelected(order)}
                    >
                      View
                    </Button>
                    {canPack && canMarkReady(order) ? (
                      <Button
                        size="sm"
                        onClick={() => requestPack(order)}
                        disabled={packingId === order.id}
                        data-testid={`field-sales-pack-${order.id}`}
                      >
                        <PackageCheck className="h-4 w-4" />
                        {packingId === order.id ? 'Packing…' : 'Mark ready'}
                      </Button>
                    ) : null}
                  </DataTableCell>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </ListPaginationRail>
      )}

      {selected ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg bg-background shadow-lg border">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div>
                <h2 className="text-lg font-semibold">Order #{selected.id}</h2>
                <p className="text-sm text-muted-foreground">
                  {STATUS_LABELS[selected.status] || selected.status}
                  {selected.customer_name ? ` · ${selected.customer_name}` : ''}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
            <div className="max-h-[60vh] overflow-auto p-4 space-y-3">
              <div className="text-sm">
                <div className="font-medium mb-1">Location</div>
                <div className="text-muted-foreground">
                  {selected.site_detail?.label || 'Delivery pin'}
                  {selected.site_detail?.latitude != null ? (
                    <div>
                      {selected.site_detail.latitude}, {selected.site_detail.longitude}
                    </div>
                  ) : null}
                  {selected.site_detail?.landmark ? (
                    <div>{selected.site_detail.landmark}</div>
                  ) : null}
                </div>
              </div>
              <div>
                <div className="font-medium text-sm mb-2">Products</div>
                <ul className="space-y-2">
                  {(selected.lines || []).map((line) => (
                    <li
                      key={line.id || `${line.product_id}-${line.variant_id}`}
                      className="flex justify-between gap-3 text-sm border-b pb-2"
                    >
                      <div>
                        <div>{line.product_name}</div>
                        <div className="text-muted-foreground">
                          {line.quantity} × {formatCurrency(line.unit_price)}
                        </div>
                      </div>
                      <div className="font-medium">
                        {formatCurrency(
                          line.line_total
                            ?? Number(line.quantity) * Number(line.unit_price),
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              {selected.notes ? (
                <div className="text-sm">
                  <div className="font-medium">Notes</div>
                  <p className="text-muted-foreground">{selected.notes}</p>
                </div>
              ) : null}
              {selected.assigned_delivery_agent_name ? (
                <div className="text-sm">
                  <div className="font-medium">Delivery driver</div>
                  <p className="text-muted-foreground">
                    {selected.assigned_delivery_agent_name}
                  </p>
                </div>
              ) : null}
              {canPack && canAssignDriver(selected) ? (
                <div className="text-sm space-y-2">
                  <div className="font-medium">Assign delivery driver</div>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={selectedDriverId}
                    onChange={(e) => setSelectedDriverId(e.target.value)}
                    data-testid="field-sales-driver-select"
                  >
                    <option value="">Select driver…</option>
                    {drivers.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.display_name || d.username}
                      </option>
                    ))}
                  </select>
                  {drivers.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No drivers yet. Add one so you can assign this order.
                    </p>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddDriver(true)}
                    data-testid="field-sales-add-driver-detail"
                  >
                    <Plus className="h-4 w-4" />
                    Add driver
                  </Button>
                </div>
              ) : null}
            </div>
            <div className="flex justify-end gap-2 border-t px-4 py-3">
              {canPack && canMarkReady(selected) ? (
                <Button
                  onClick={() => requestPack(selected)}
                  disabled={packingId === selected.id}
                  data-testid="field-sales-pack-detail"
                >
                  <PackageCheck className="h-4 w-4" />
                  Mark ready for pickup
                </Button>
              ) : null}
              {canPack && canAssignDriver(selected) ? (
                <Button
                  onClick={() => requestAssign(selected)}
                  disabled={assigningId === selected.id}
                  data-testid="field-sales-assign"
                >
                  {assigningId === selected.id ? 'Assigning…' : 'Assign driver'}
                </Button>
              ) : null}
              <Button variant="outline" onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <AddDriverDialog
        open={showAddDriver}
        onClose={() => setShowAddDriver(false)}
        onCreated={(driver) => {
          if (!driver?.id) return;
          setDrivers((prev) => {
            if (prev.some((d) => d.id === driver.id)) return prev;
            return [...prev, driver];
          });
          setSelectedDriverId(String(driver.id));
        }}
      />

      <CommitConfirm
        open={!!pending}
        onOpenChange={(open) => {
          if (!open && packingId == null && assigningId == null) setPending(null);
        }}
        title={pending?.type === 'assign' ? 'Assign this order?' : 'Pack this order?'}
        description={
          pending?.type === 'assign'
            ? 'The driver will see it on their route after you confirm.'
            : 'Stock will be allocated and the order marked ready for pickup.'
        }
        rows={pendingRows}
        onConfirm={confirmPending}
        submitting={packingId != null || assigningId != null}
        confirmText={pending?.type === 'assign' ? 'Confirm & assign' : 'Confirm & pack'}
      />
    </PageShell>
  );
};

export default FieldSalesPage;
