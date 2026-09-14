import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MapPin, PackageCheck, RefreshCw } from 'lucide-react';
import { dispatchAPI } from '../../services/api';
import { DEFAULT_PAGE_SIZE } from '../../config/pagination';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
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

function orderLineSummary(order) {
  const lines = Array.isArray(order?.lines) ? order.lines : [];
  if (!lines.length) return '—';
  const qty = lines.reduce((sum, line) => sum + Number(line.quantity || 0), 0);
  const names = lines
    .slice(0, 2)
    .map((line) => line.product_name || `Product #${line.product_id}`)
    .join(', ');
  const more = lines.length > 2 ? ` +${lines.length - 2}` : '';
  return `${names}${more} · qty ${qty}`;
}

function orderTotal(order) {
  const lines = Array.isArray(order?.lines) ? order.lines : [];
  return lines.reduce((sum, line) => {
    const qty = Number(line.quantity || 0);
    const price = Number(line.unit_price || 0);
    const total = line.line_total != null ? Number(line.line_total) : qty * price;
    return sum + (Number.isFinite(total) ? total : 0);
  }, 0);
}

function canMarkReady(order) {
  return ['submitted', 'packing'].includes(order?.status);
}

const FieldSalesPage = () => {
  const { permissions } = getStoredAuth();
  const canPack = hasPermission(permissions, 'dispatch', 'update');
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [packingId, setPackingId] = useState(null);
  const [selected, setSelected] = useState(null);
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

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPagination((prev) => ({ ...prev, page: 1 }));
  };

  const handleMarkReady = async (order) => {
    if (!canPack || !canMarkReady(order)) return;
    setPackingId(order.id);
    try {
      await dispatchAPI.pack(order.id);
      toast.success(`Order #${order.id} marked ready for pickup`);
      await loadOrders();
      if (selected?.id === order.id) {
        const refreshed = await dispatchAPI.get(order.id);
        setSelected(refreshed.data);
      }
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
        description="Visit orders from the field — filter by day, status, or customer, and mark packed orders ready for pickup."
      >
        <Button variant="outline" onClick={loadOrders} disabled={loading}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </PageHeader>

      <FilterBar>
        <FilterField label="From">
          <Input
            type="date"
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
          />
        </FilterField>
        <FilterField label="To">
          <Input
            type="date"
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
          />
        </FilterField>
        <FilterField label="Status">
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={filters.status}
            onChange={(e) => handleFilterChange('status', e.target.value)}
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
                    {orderLineSummary(order)}
                  </DataTableCell>
                  <DataTableCell>{formatCurrency(orderTotal(order))}</DataTableCell>
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
                        onClick={() => handleMarkReady(order)}
                        disabled={packingId === order.id}
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
            </div>
            <div className="flex justify-end gap-2 border-t px-4 py-3">
              {canPack && canMarkReady(selected) ? (
                <Button
                  onClick={() => handleMarkReady(selected)}
                  disabled={packingId === selected.id}
                >
                  <PackageCheck className="h-4 w-4" />
                  Mark ready for pickup
                </Button>
              ) : null}
              <Button variant="outline" onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </PageShell>
  );
};

export default FieldSalesPage;
