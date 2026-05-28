import React, { useState, useEffect, useMemo } from 'react';
import { FolderTree, Pencil, Plus, Trash2 } from 'lucide-react';
import { categoriesAPI } from '../../services/api';
import { formatNumber } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import CategoryForm from './CategoryForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  SearchField,
  FilterPills,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
  ActiveStatusBadge,
} from '../page';

const FILTER_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
];

const Categories = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState('all');
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    loadCategories();
  }, [filterActive]);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterActive !== 'all') {
        params.is_active = filterActive === 'active';
      }
      const response = await categoriesAPI.list(params);
      const categoriesData = response.data.results || response.data || [];
      setCategories(Array.isArray(categoriesData) ? categoriesData : []);
    } catch (error) {
      console.error('Error loading categories:', error);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (id) => setConfirmDelete(id);

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;
    try {
      await categoriesAPI.delete(confirmDelete);
      loadCategories();
      toast.success('Category deleted successfully');
    } catch (error) {
      toast.error(
        error.response?.data?.error ||
          error.response?.data?.detail ||
          'Failed to delete category'
      );
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleToggleActive = async (category) => {
    try {
      await categoriesAPI.update(category.id, {
        ...category,
        is_active: !category.is_active,
      });
      loadCategories();
      toast.success(
        `Category ${!category.is_active ? 'activated' : 'deactivated'} successfully`
      );
    } catch {
      toast.error('Failed to update category');
    }
  };

  const categoryNameById = useMemo(() => {
    const map = {};
    categories.forEach((c) => {
      map[c.id] = c.name;
    });
    return map;
  }, [categories]);

  const filteredCategories = categories.filter((cat) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      cat.name.toLowerCase().includes(query) ||
      (cat.description && cat.description.toLowerCase().includes(query))
    );
  });

  const openCreate = () => {
    setEditingCategory(null);
    setShowForm(true);
  };

  const openEdit = (category) => {
    setEditingCategory(category);
    setShowForm(true);
  };

  if (loading) {
    return (
      <Layout>
        <PageLoading rows={8} />
      </Layout>
    );
  }

  return (
    <Layout>
      <PageShell>
        <PageHeader
          title="Categories"
          description="Organize products into groups and subcategories."
        >
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Add category
          </Button>
        </PageHeader>

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search categories…"
            className="max-w-md"
          />
          <FilterPills
            options={FILTER_OPTIONS}
            value={filterActive}
            onChange={setFilterActive}
          />
        </FilterBar>

        {filteredCategories.length === 0 ? (
          <EmptyState
            icon={FolderTree}
            title={searchQuery ? 'No matches' : 'No categories yet'}
            description={
              searchQuery
                ? 'Try a different search term.'
                : 'Create your first category to group products.'
            }
            actionLabel={!searchQuery ? 'Add category' : undefined}
            onAction={!searchQuery ? openCreate : undefined}
          />
        ) : (
          <DataTable>
            <DataTableHeader>
              <DataTableHead>Name</DataTableHead>
              <DataTableHead>Parent</DataTableHead>
              <DataTableHead>Description</DataTableHead>
              <DataTableHead align="right">Products</DataTableHead>
              <DataTableHead align="right">Subcats</DataTableHead>
              <DataTableHead>Status</DataTableHead>
              <DataTableHead align="right">Actions</DataTableHead>
            </DataTableHeader>
            <DataTableBody>
              {filteredCategories.map((category) => (
                <DataTableRow key={category.id} inactive={!category.is_active}>
                  <DataTableCell className="font-medium">{category.name}</DataTableCell>
                  <DataTableCell className="text-muted-foreground">
                    {category.parent
                      ? categoryNameById[category.parent] || '—'
                      : '—'}
                  </DataTableCell>
                  <DataTableCell className="max-w-[200px] truncate text-muted-foreground">
                    {category.description || '—'}
                  </DataTableCell>
                  <DataTableCell align="right">
                    {formatNumber(category.product_count || 0)}
                  </DataTableCell>
                  <DataTableCell align="right">
                    {formatNumber(category.children_count || 0)}
                  </DataTableCell>
                  <DataTableCell>
                    <ActiveStatusBadge active={category.is_active} />
                  </DataTableCell>
                  <DataTableCell align="right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(category)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleActive(category)}
                      >
                        {category.is_active ? 'Off' : 'On'}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(category.id)}
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

        {showForm && (
          <CategoryForm
            category={editingCategory}
            onClose={() => {
              setShowForm(false);
              setEditingCategory(null);
            }}
            onSave={() => {
              setShowForm(false);
              setEditingCategory(null);
              loadCategories();
            }}
            categories={categories}
          />
        )}

        <ConfirmDialog
          isOpen={!!confirmDelete}
          title="Delete category"
          message="Products in this category will have their category cleared. This cannot be undone."
          onConfirm={confirmDeleteAction}
          onCancel={() => setConfirmDelete(null)}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </PageShell>
    </Layout>
  );
};

export default Categories;
