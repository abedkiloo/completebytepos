import React, { useCallback, useEffect, useState } from 'react';
import { FolderTree, Pencil, Plus, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { expensesAPI } from '../../services/api';
import { CATALOG_FETCH_PAGE_SIZE } from '../../config/pagination';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { formatApiError } from '../../utils/apiErrors';
import { isSuperAdminFromStorage } from '../../utils/navAccess';
import { canDeleteExpenseCategory } from '../../utils/expenseCategories';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
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
  ActiveStatusBadge,
} from '../page';

const EMPTY_FORM = { name: '', description: '', is_active: true };

export default function ExpenseCategories() {
  const canDelete = isSuperAdminFromStorage();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const loadCategories = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page_size: CATALOG_FETCH_PAGE_SIZE };
      if (activeFilter === 'active') params.is_active = 'true';
      if (activeFilter === 'inactive') params.is_active = 'false';
      if (search.trim()) params.search = search.trim();
      const response = await expensesAPI.categories.list(params);
      const data = response.data.results || response.data || [];
      setCategories(Array.isArray(data) ? data : []);
    } catch (error) {
      setCategories([]);
      toast.error(formatApiError(error, 'Failed to load expense categories'));
    } finally {
      setLoading(false);
    }
  }, [activeFilter, search]);

  useEffect(() => {
    const t = setTimeout(loadCategories, 200);
    return () => clearTimeout(t);
  }, [loadCategories]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (category) => {
    setEditing(category);
    setForm({
      name: category.name || '',
      description: category.description || '',
      is_active: category.is_active !== false,
    });
    setShowForm(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error('Category name is required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        is_active: Boolean(form.is_active),
      };
      if (editing) {
        await expensesAPI.categories.update(editing.id, payload);
        toast.success('Category updated');
      } else {
        const response = await expensesAPI.categories.create(payload);
        if (response.status === 200) {
          toast.success(`Using existing category “${response.data.name}”`);
        } else {
          toast.success('Category created');
        }
      }
      setShowForm(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      loadCategories();
    } catch (error) {
      toast.error(formatApiError(error, 'Failed to save category'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await expensesAPI.categories.delete(confirmDelete.id);
      toast.success(`Deleted “${confirmDelete.name}”`);
      setConfirmDelete(null);
      loadCategories();
    } catch (error) {
      toast.error(formatApiError(error, 'Could not delete category'));
    }
  };

  if (loading && categories.length === 0) {
    return <PageLoading rows={8} />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Expense categories"
        description="Organize expenses by category. Unused categories can be deleted by an admin."
      >
        <Link to="/expenses">
          <Button type="button" variant="outline">
            Back to expenses
          </Button>
        </Link>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add category
        </Button>
      </PageHeader>

      <FilterBar>
        <FilterField label="Search" className="min-w-[200px] flex-[2]">
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search categories…"
          />
        </FilterField>
        <FilterField label="Status">
          <select
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </FilterField>
      </FilterBar>

      {categories.length === 0 ? (
        <EmptyState
          icon={FolderTree}
          title="No expense categories"
          description="Create categories to classify spending."
          actionLabel="Add category"
          onAction={openCreate}
        />
      ) : (
        <DataTable>
          <DataTableHeader>
            <DataTableHead>Name</DataTableHead>
            <DataTableHead>Description</DataTableHead>
            <DataTableHead align="right">Expenses</DataTableHead>
            <DataTableHead>Status</DataTableHead>
            <DataTableHead align="right">Actions</DataTableHead>
          </DataTableHeader>
          <DataTableBody>
            {categories.map((category) => {
              const showDelete = canDeleteExpenseCategory(category, {
                isAdmin: canDelete,
              });
              const used = Number(category.expense_count || 0) > 0;
              return (
                <DataTableRow key={category.id}>
                  <DataTableCell className="font-medium">{category.name}</DataTableCell>
                  <DataTableCell className="max-w-[280px] truncate text-muted-foreground">
                    {category.description || '—'}
                  </DataTableCell>
                  <DataTableCell align="right" className="tabular-nums">
                    {category.expense_count ?? 0}
                  </DataTableCell>
                  <DataTableCell>
                    <ActiveStatusBadge active={category.is_active !== false} />
                  </DataTableCell>
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(category)}
                        aria-label={`Edit ${category.name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      {canDelete ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          disabled={!showDelete}
                          title={
                            used
                              ? 'Category is in use — deactivate instead'
                              : `Delete ${category.name}`
                          }
                          onClick={() => setConfirmDelete(category)}
                          aria-label={`Delete ${category.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </div>
                  </DataTableCell>
                </DataTableRow>
              );
            })}
          </DataTableBody>
        </DataTable>
      )}

      {showForm ? (
        <div className="slide-in-overlay" onClick={() => setShowForm(false)}>
          <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
            <div className="slide-in-panel-header">
              <h2>{editing ? 'Edit category' : 'New expense category'}</h2>
              <button
                type="button"
                className="slide-in-panel-close"
                onClick={() => setShowForm(false)}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleSave} className="slide-in-panel-body space-y-4">
              <div className="space-y-1">
                <Label htmlFor="expense-cat-name">Name *</Label>
                <Input
                  id="expense-cat-name"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="expense-cat-desc">Description</Label>
                <textarea
                  id="expense-cat-desc"
                  className="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={form.description}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, description: e.target.value }))
                  }
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, is_active: e.target.checked }))
                  }
                />
                Active
              </label>
              <div className="slide-in-panel-footer">
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={saving}>
                  {saving ? 'Saving…' : editing ? 'Update' : 'Create'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete expense category"
        message={
          confirmDelete
            ? `Delete “${confirmDelete.name}”? Only unused categories can be removed.`
            : ''
        }
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
    </PageShell>
  );
}
