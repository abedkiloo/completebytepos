import React, { useState, useEffect, useCallback } from 'react';
import { Palette, Ruler, Plus, Pencil, Trash2 } from 'lucide-react';
import { sizesAPI, colorsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { useProductVariantsEnabled } from '../../hooks/useProductVariantsEnabled';
import { Button } from '../ui/button';
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

const TABS = [
  { id: 'sizes', label: 'Sizes', icon: Ruler },
  { id: 'colors', label: 'Colors', icon: Palette },
];

const ProductAttributes = () => {
  const variantsEnabled = useProductVariantsEnabled();
  const [tab, setTab] = useState('sizes');
  const [sizes, setSizes] = useState([]);
  const [colors, setColors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', code: '', hex_code: '', display_order: 0, is_active: true });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, cRes] = await Promise.all([
        sizesAPI.list(),
        colorsAPI.list(),
      ]);
      setSizes(sRes.data.results || sRes.data || []);
      setColors(cRes.data.results || cRes.data || []);
    } catch {
      toast.error('Failed to load sizes and colors');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({
      name: '',
      code: '',
      hex_code: '',
      display_order: tab === 'sizes' ? sizes.length + 1 : 0,
      is_active: true,
    });
    setFormOpen(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    setForm({
      name: row.name || '',
      code: row.code || '',
      hex_code: row.hex_code || '',
      display_order: row.display_order ?? 0,
      is_active: row.is_active !== false,
    });
    setFormOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error('Name is required');
      return;
    }
    try {
      if (tab === 'sizes') {
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
      setFormOpen(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.name?.[0] || err.response?.data?.detail || 'Save failed');
    }
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete "${row.name}"? Products using it may be affected.`)) return;
    try {
      if (tab === 'sizes') await sizesAPI.delete(row.id);
      else await colorsAPI.delete(row.id);
      toast.success('Deleted');
      load();
    } catch {
      toast.error('Delete failed — item may be in use');
    }
  };

  if (!variantsEnabled) {
    return (
      <PageShell>
        <PageHeader
          title="Sizes & colors"
          description="Variant options used when adding products with size/color variants."
        />
        <EmptyState
          icon={Palette}
          title="Product variants are disabled"
          description='Enable Products → Product Variants in Module Settings, then return here to add sizes and colors.'
        />
      </PageShell>
    );
  }

  if (loading) return <PageLoading rows={6} />;

  const rows = tab === 'sizes' ? sizes : colors;

  return (
    <PageShell>
      <PageHeader
        title="Sizes & colors"
        description="Define options here first, then pick them on each product under “This product has size/color variants”."
      >
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add {tab === 'sizes' ? 'size' : 'color'}
        </Button>
      </PageHeader>

      <div className="mb-4 flex gap-2 border-b border-border pb-2">
        {TABS.map(({ id, label, icon: Icon }) => (
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

      {rows.length === 0 ? (
        <EmptyState
          icon={tab === 'sizes' ? Ruler : Palette}
          title={`No ${tab} yet`}
          description={`Add ${tab} before assigning variants on products.`}
          actionLabel={`Add ${tab === 'sizes' ? 'size' : 'color'}`}
          onAction={openCreate}
        />
      ) : (
        <DataTable>
          <DataTableHeader>
            <DataTableHead>Name</DataTableHead>
            {tab === 'sizes' ? <DataTableHead>Code</DataTableHead> : <DataTableHead>Hex</DataTableHead>}
            {tab === 'sizes' && <DataTableHead align="right">Order</DataTableHead>}
            <DataTableHead>Status</DataTableHead>
            <DataTableHead align="right">Actions</DataTableHead>
          </DataTableHeader>
          <DataTableBody>
            {rows.map((row) => (
              <DataTableRow key={row.id} inactive={!row.is_active}>
                <DataTableCell className="font-medium">{row.name}</DataTableCell>
                {tab === 'sizes' ? (
                  <DataTableCell>{row.code}</DataTableCell>
                ) : (
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
                {tab === 'sizes' && (
                  <DataTableCell align="right">{row.display_order ?? 0}</DataTableCell>
                )}
                <DataTableCell>
                  <ActiveStatusBadge active={row.is_active} />
                </DataTableCell>
                <DataTableCell align="right">
                  <div className="flex justify-end gap-1">
                    <Button variant="ghost" size="sm" onClick={() => openEdit(row)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => handleDelete(row)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </DataTableCell>
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
                {editing ? 'Edit' : 'Add'} {tab === 'sizes' ? 'size' : 'color'}
              </h2>
              <button type="button" className="slide-in-panel-close" onClick={() => setFormOpen(false)}>
                ×
              </button>
            </div>
            <form onSubmit={handleSave} className="slide-in-panel-body category-form">
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
              <button type="button" className="btn btn-primary" onClick={handleSave}>
                {editing ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
};

export default ProductAttributes;
