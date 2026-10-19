import React, { useState, useEffect, useCallback } from 'react';
import { Palette, Ruler, Plus, Pencil, Trash2, Scale } from 'lucide-react';
import { sizesAPI, colorsAPI, productsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { CATALOG_FETCH_PAGE_SIZE } from '../../config/pagination';
import { useProductVariantsEnabled } from '../../hooks/useProductVariantsEnabled';
import { isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { Button } from '../ui/button';
import CommitConfirm from '../Shared/CommitConfirm';
import { attributeDeleteRows, attributeSaveRows } from '../../utils/formCommitSummary';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ActiveStatusBadge,
} from '../page';
import { ListSortBar } from '../page/ListSortBar';
import { useListOrdering } from '../../hooks/useListOrdering';
import { withListOrdering } from '../../utils/listOrdering';

const ALL_TABS = [
  { id: 'units', label: 'Units', icon: Scale },
  { id: 'sizes', label: 'Sizes', icon: Ruler },
  { id: 'colors', label: 'Colors', icon: Palette },
];

const emptyForm = (tab, nextOrder = 0) => {
  if (tab === 'units') {
    return { code: '', label: '', display_order: nextOrder, is_active: true };
  }
  return {
    name: '',
    code: '',
    hex_code: '',
    display_order: nextOrder,
    is_active: true,
  };
};

const ProductAttributes = () => {
  const variantsEnabled = useProductVariantsEnabled();
  const canManageUnits = isManagerOrAdminFromStorage();
  const tabs = variantsEnabled
    ? ALL_TABS
    : ALL_TABS.filter((t) => t.id === 'units');
  const [tab, setTab] = useState('units');
  const [sizes, setSizes] = useState([]);
  const [colors, setColors] = useState([]);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(() => emptyForm('units'));
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [saving, setSaving] = useState(false);
  const { ordering, setOrdering } = useListOrdering();
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!tabs.some((t) => t.id === tab)) {
      setTab(tabs[0]?.id || 'units');
    }
  }, [tabs, tab]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const requests = [productsAPI.units.list()];
      if (variantsEnabled) {
        requests.push(
          sizesAPI.list(withListOrdering({ page_size: CATALOG_FETCH_PAGE_SIZE }, ordering)),
          colorsAPI.list(withListOrdering({ page_size: CATALOG_FETCH_PAGE_SIZE }, ordering))
        );
      }
      const [uRes, sRes, cRes] = await Promise.all(requests);
      setUnits(uRes.data.results || uRes.data || []);
      if (variantsEnabled) {
        setSizes(sRes.data.results || sRes.data || []);
        setColors(cRes.data.results || cRes.data || []);
      } else {
        setSizes([]);
        setColors([]);
      }
    } catch {
      toast.error('Failed to load catalog options');
    } finally {
      setLoading(false);
    }
  }, [ordering, variantsEnabled]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    if (tab === 'units' && !canManageUnits) {
      toast.error('Only managers and admins can add units');
      return;
    }
    setEditing(null);
    const nextOrder =
      tab === 'sizes' ? sizes.length + 1 : tab === 'units' ? units.length + 1 : 0;
    setForm(emptyForm(tab, nextOrder));
    setFormOpen(true);
  };

  const openEdit = (row) => {
    if (tab === 'units' && !canManageUnits) {
      toast.error('Only managers and admins can edit units');
      return;
    }
    setEditing(row);
    if (tab === 'units') {
      setForm({
        code: row.code || '',
        label: row.label || '',
        display_order: row.display_order ?? 0,
        is_active: row.is_active !== false,
      });
    } else {
      setForm({
        name: row.name || '',
        code: row.code || '',
        hex_code: row.hex_code || '',
        display_order: row.display_order ?? 0,
        is_active: row.is_active !== false,
      });
    }
    setFormOpen(true);
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (tab === 'units') {
      if (!form.label.trim()) {
        toast.error('Label is required');
        return;
      }
      if (!editing && !form.code.trim()) {
        toast.error('Code is required');
        return;
      }
    } else if (!form.name.trim()) {
      toast.error('Name is required');
      return;
    }
    setShowCommitConfirm(true);
  };

  const confirmSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      if (tab === 'units') {
        const payload = {
          label: form.label.trim(),
          display_order: Number(form.display_order) || 0,
          is_active: form.is_active,
        };
        if (editing) {
          await productsAPI.units.patch(editing.id, payload);
        } else {
          await productsAPI.units.create({
            ...payload,
            code: form.code.trim().toLowerCase(),
          });
        }
      } else if (tab === 'sizes') {
        const payload = {
          name: form.name.trim(),
          code: (form.code || form.name).trim().slice(0, 10).toUpperCase(),
          display_order: Number(form.display_order) || 0,
          is_active: form.is_active,
        };
        if (editing) await sizesAPI.update(editing.id, payload);
        else await sizesAPI.create(payload);
      } else {
        const payload = {
          name: form.name.trim(),
          hex_code: form.hex_code.trim(),
          is_active: form.is_active,
        };
        if (editing) await colorsAPI.update(editing.id, payload);
        else await colorsAPI.create(payload);
      }
      toast.success(editing ? 'Updated' : 'Created');
      setShowCommitConfirm(false);
      setFormOpen(false);
      load();
    } catch (err) {
      const data = err.response?.data;
      toast.error(
        data?.code?.[0] ||
          data?.label?.[0] ||
          data?.name?.[0] ||
          data?.detail ||
          data?.error ||
          'Save failed'
      );
    } finally {
      setSaving(false);
    }
  };

  const requestDelete = (row) => {
    if (tab === 'units' && !canManageUnits) {
      toast.error('Only managers and admins can delete units');
      return;
    }
    setPendingDelete(row);
  };

  const confirmDelete = async () => {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    try {
      if (tab === 'units') await productsAPI.units.delete(pendingDelete.id);
      else if (tab === 'sizes') await sizesAPI.delete(pendingDelete.id);
      else await colorsAPI.delete(pendingDelete.id);
      toast.success('Deleted');
      setPendingDelete(null);
      load();
    } catch {
      toast.error('Delete failed — item may be in use');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <PageLoading rows={6} />;

  const rows = tab === 'units' ? units : tab === 'sizes' ? sizes : colors;
  const kindLabel = tab === 'units' ? 'unit' : tab === 'sizes' ? 'size' : 'color';
  const canWrite = tab !== 'units' || canManageUnits;

  return (
    <PageShell>
      <PageHeader
        title="Sizes, colors & units"
        description={
          variantsEnabled
            ? 'Manage sell units and size/color options used on products and variants.'
            : 'Manage sell units (piece, kg, roll, …). Enable Product Variants in Module Settings for sizes and colors.'
        }
      >
        {canWrite ? (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Add {kindLabel}
          </Button>
        ) : null}
      </PageHeader>

      <div className="mb-4 flex gap-2 border-b border-border pb-2">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              tab === id
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>
      {tab !== 'units' ? (
        <div className="mb-4">
          <ListSortBar value={ordering} onChange={setOrdering} />
        </div>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState
          icon={tab === 'units' ? Scale : tab === 'sizes' ? Ruler : Palette}
          title={`No ${tab} yet`}
          description={
            tab === 'units'
              ? 'Add units before assigning them on products.'
              : `Add ${tab} before assigning variants on products.`
          }
          actionLabel={canWrite ? `Add ${kindLabel}` : undefined}
          onAction={canWrite ? openCreate : undefined}
        />
      ) : (
        <DataTable>
          <DataTableHeader>
            <DataTableHead>
              {tab === 'units' ? 'Label' : 'Name'}
            </DataTableHead>
            <DataTableHead>Code</DataTableHead>
            {(tab === 'sizes' || tab === 'units') && (
              <DataTableHead align="right">Order</DataTableHead>
            )}
            {tab === 'colors' && <DataTableHead>Hex</DataTableHead>}
            <DataTableHead>Status</DataTableHead>
            {canWrite ? <DataTableHead align="right">Actions</DataTableHead> : null}
          </DataTableHeader>
          <DataTableBody>
            {rows.map((row) => (
              <DataTableRow key={row.id} inactive={!row.is_active}>
                <DataTableCell className="font-medium">
                  {tab === 'units' ? row.label : row.name}
                </DataTableCell>
                <DataTableCell>{row.code || '—'}</DataTableCell>
                {(tab === 'sizes' || tab === 'units') && (
                  <DataTableCell align="right">{row.display_order ?? 0}</DataTableCell>
                )}
                {tab === 'colors' && (
                  <DataTableCell>
                    {row.hex_code ? (
                      <span className="inline-flex items-center gap-2">
                        <span
                          className="inline-block h-4 w-4 rounded border border-border"
                          style={{ backgroundColor: row.hex_code }}
                        />
                        {row.hex_code}
                      </span>
                    ) : (
                      '—'
                    )}
                  </DataTableCell>
                )}
                <DataTableCell>
                  <ActiveStatusBadge active={row.is_active} />
                </DataTableCell>
                {canWrite ? (
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => requestDelete(row)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </DataTableCell>
                ) : null}
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
      )}

      {formOpen && (
        <div className="slide-in-overlay" onClick={() => setFormOpen(false)}>
          <div className="slide-in-panel max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="slide-in-panel-header">
              <h2>
                {editing ? 'Edit' : 'Add'} {kindLabel}
              </h2>
              <button type="button" className="slide-in-panel-close" onClick={() => setFormOpen(false)}>
                ×
              </button>
            </div>
            <form onSubmit={handleSave} className="slide-in-panel-body category-form">
              {tab === 'units' ? (
                <>
                  <div className="form-group">
                    <label>Label *</label>
                    <input
                      value={form.label}
                      onChange={(e) => setForm({ ...form, label: e.target.value })}
                      placeholder="e.g. Spool"
                      required
                      autoFocus
                    />
                  </div>
                  <div className="form-group">
                    <label>Code *</label>
                    <input
                      value={form.code}
                      onChange={(e) => setForm({ ...form, code: e.target.value })}
                      placeholder="e.g. spool"
                      required={!editing}
                      disabled={!!editing}
                    />
                    {editing ? (
                      <small className="form-text text-muted">Code cannot change after create.</small>
                    ) : null}
                  </div>
                  <div className="form-group">
                    <label>Display order</label>
                    <input
                      type="number"
                      value={form.display_order}
                      onChange={(e) => setForm({ ...form, display_order: e.target.value })}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="form-group">
                    <label>Name *</label>
                    <input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      required
                      autoFocus
                    />
                  </div>
                  {tab === 'sizes' ? (
                    <>
                      <div className="form-group">
                        <label>Code</label>
                        <input
                          value={form.code}
                          onChange={(e) => setForm({ ...form, code: e.target.value })}
                          placeholder="e.g. M"
                        />
                      </div>
                      <div className="form-group">
                        <label>Display order</label>
                        <input
                          type="number"
                          value={form.display_order}
                          onChange={(e) => setForm({ ...form, display_order: e.target.value })}
                        />
                      </div>
                    </>
                  ) : (
                    <div className="form-group">
                      <label>Hex color (optional)</label>
                      <input
                        value={form.hex_code}
                        onChange={(e) => setForm({ ...form, hex_code: e.target.value })}
                        placeholder="#FF0000"
                      />
                    </div>
                  )}
                </>
              )}
              <div className="form-group">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  />
                  Active
                </label>
              </div>
            </form>
            <div className="slide-in-panel-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setFormOpen(false)}>
                Cancel
              </button>
              <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {editing ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(open) => {
          if (!open && !saving) setShowCommitConfirm(false);
        }}
        title={editing ? `Update this ${kindLabel}?` : `Create this ${kindLabel}?`}
        description="Review the details, then confirm to save."
        rows={
          tab === 'units'
            ? [
                { label: 'Label', value: form.label },
                { label: 'Code', value: form.code || editing?.code || '—' },
                { label: 'Active', value: form.is_active ? 'Yes' : 'No' },
              ]
            : attributeSaveRows(form, { kind: tab, isEdit: !!editing })
        }
        submitting={saving}
        confirmText={editing ? 'Confirm & update' : 'Confirm & create'}
        onConfirm={confirmSave}
      />
      <CommitConfirm
        open={!!pendingDelete}
        onOpenChange={(open) => {
          if (!open && !deleting) setPendingDelete(null);
        }}
        title={`Delete this ${kindLabel}?`}
        description="Products using it may be affected."
        rows={
          tab === 'units'
            ? [
                { label: 'Label', value: pendingDelete?.label || '—' },
                { label: 'Code', value: pendingDelete?.code || '—' },
              ]
            : attributeDeleteRows(pendingDelete || {}, tab)
        }
        submitting={deleting}
        confirmText="Confirm & delete"
        variant="danger"
        onConfirm={confirmDelete}
      />
    </PageShell>
  );
};

export default ProductAttributes;
