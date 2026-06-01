import React, { useState, useEffect, useMemo } from 'react';
import { FolderTree, Layers, Pencil, Plus, Trash2 } from 'lucide-react';
import { categoriesAPI } from '../../services/api';
import { formatNumber } from '../../utils/formatters';
import CategoryForm from './CategoryForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  partitionCategories,
  flattenCategoryTree,
  filterCategoriesForSearch,
  filterByLevel,
} from '../../utils/categoryTree';
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

const LEVEL_OPTIONS = [
  { value: 'all', label: 'All levels' },
  { value: 'parents', label: 'Categories only' },
  { value: 'subcategories', label: 'Subcategories only' },
];

const Categories = () => {
  const { settings } = useStoreSettings();
  const hideStatusToggles = settings.hide_entity_status_toggles;

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [initialParentId, setInitialParentId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
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

  const displayRows = useMemo(() => {
    let list = categories;
    list = filterByLevel(list, levelFilter);
    list = filterCategoriesForSearch(list, searchQuery);
    const { parents, childrenByParent, orphans } = partitionCategories(list);
    return flattenCategoryTree(parents, childrenByParent, orphans);
  }, [categories, searchQuery, levelFilter]);

  const stats = useMemo(() => {
    const parents = categories.filter((c) => !c.parent).length;
    const subs = categories.filter((c) => c.parent).length;
    return { parents, subs, total: categories.length };
  }, [categories]);

  const openCreate = (parentId = null) => {
    setEditingCategory(null);
    setInitialParentId(parentId);
    setShowForm(true);
  };

  const openEdit = (category) => {
    setEditingCategory(category);
    setInitialParentId(null);
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingCategory(null);
    setInitialParentId(null);
  };

  if (loading) {
    return <PageLoading rows={8} />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Categories"
        description={`${stats.parents} categories · ${stats.subs} subcategories`}
      >
        <Button onClick={() => openCreate(null)}>
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
        <FilterPills
          options={LEVEL_OPTIONS}
          value={levelFilter}
          onChange={setLevelFilter}
        />
      </FilterBar>

      {displayRows.length === 0 ? (
        <EmptyState
          icon={FolderTree}
          title={searchQuery ? 'No matches' : 'No categories yet'}
          description={
            searchQuery
              ? 'Try a different search term or level filter.'
              : 'Create a top-level category, then add subcategories under it.'
          }
          actionLabel={!searchQuery ? 'Add category' : undefined}
          onAction={!searchQuery ? () => openCreate(null) : undefined}
        />
      ) : (
        <DataTable>
          <DataTableHeader>
            <DataTableHead>Name</DataTableHead>
            <DataTableHead>Type</DataTableHead>
            <DataTableHead>Under</DataTableHead>
            <DataTableHead>Description</DataTableHead>
            <DataTableHead align="right">Products</DataTableHead>
            <DataTableHead align="right">Subcats</DataTableHead>
            {!hideStatusToggles && <DataTableHead>Status</DataTableHead>}
            <DataTableHead align="right">Actions</DataTableHead>
          </DataTableHeader>
          <DataTableBody>
            {displayRows.map(({ category, depth, isParent, parentName, isOrphan }) => (
              <DataTableRow
                key={category.id}
                inactive={!category.is_active}
                className={depth > 0 ? 'bg-muted/30' : undefined}
              >
                <DataTableCell className="font-medium">
                  <div
                    className="flex items-center gap-2"
                    style={{ paddingLeft: depth > 0 ? '1.5rem' : 0 }}
                  >
                    {depth > 0 ? (
                      <Layers className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                    ) : (
                      <FolderTree className="h-4 w-4 shrink-0 text-primary" aria-hidden />
                    )}
                    <span>{category.name}</span>
                  </div>
                </DataTableCell>
                <DataTableCell>
                  {isParent ? (
                    <Badge variant="secondary">Category</Badge>
                  ) : (
                    <Badge variant="outline">Subcategory</Badge>
                  )}
                </DataTableCell>
                <DataTableCell className="text-muted-foreground">
                  {depth > 0
                    ? parentName ||
                      categoryNameById[category.parent] ||
                      (isOrphan ? 'Unknown parent' : '—')
                    : '—'}
                </DataTableCell>
                <DataTableCell className="max-w-[200px] truncate text-muted-foreground">
                  {category.description || '—'}
                </DataTableCell>
                <DataTableCell align="right">
                  {formatNumber(category.product_count || 0)}
                </DataTableCell>
                <DataTableCell align="right">
                  {isParent ? formatNumber(category.children_count || 0) : '—'}
                </DataTableCell>
                {!hideStatusToggles && (
                  <DataTableCell>
                    <ActiveStatusBadge active={category.is_active} />
                  </DataTableCell>
                )}
                <DataTableCell align="right">
                  <div className="flex flex-wrap justify-end gap-1">
                    {isParent && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs"
                        onClick={() => openCreate(category.id)}
                        title="Add subcategory"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Sub
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => openEdit(category)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    {!hideStatusToggles && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleActive(category)}
                      >
                        {category.is_active ? 'Off' : 'On'}
                      </Button>
                    )}
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
          initialParentId={initialParentId}
          onClose={closeForm}
          onSave={() => {
            closeForm();
            loadCategories();
          }}
          categories={categories}
          hideStatusToggles={hideStatusToggles}
        />
      )}

      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete category"
        message="Products linked to this category may be cleared. Subcategories under a parent must be deleted or moved first. This cannot be undone."
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
    </PageShell>
  );
};

export default Categories;
