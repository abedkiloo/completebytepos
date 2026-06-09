import React, { useState, useEffect, useMemo } from 'react';
import { FolderTree, Layers, Pencil, Plus, Trash2 } from 'lucide-react';
import { categoriesAPI } from '../../services/api';
import { formatNumber } from '../../utils/formatters';
import CategoryForm from './CategoryForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  categoryDeactivateNeedsReason,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';
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
  const makerCheckerOn = isMakerCheckerEnabled(settings);

  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [initialParentId, setInitialParentId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState('all');
  const [levelFilter, setLevelFilter] = useState('all');
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleteReason, setDeleteReason] = useState('');
  const [confirmDeactivate, setConfirmDeactivate] = useState(null);
  const [deactivateReason, setDeactivateReason] = useState('');

  useEffect(() => {
    loadCategories();
  }, [filterActive, searchQuery]);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const params = { page_size: 200 };
      if (filterActive !== 'all') {
        params.is_active = filterActive === 'active';
      }
      const q = searchQuery.trim();
      if (q) {
        params.search = q;
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
    if (makerCheckerOn && !deleteReason.trim()) {
      toast.warning('Enter a reason for deleting this category.');
      return;
    }
    try {
      const payload = makerCheckerOn ? { reason: deleteReason.trim() } : {};
      const res = await categoriesAPI.delete(confirmDelete, payload);
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else {
        toast.success('Category deleted successfully');
      }
      loadCategories();
    } catch (error) {
      toast.error(
        error.response?.data?.error ||
          error.response?.data?.detail ||
          'Failed to delete category'
      );
    } finally {
      setConfirmDelete(null);
      setDeleteReason('');
    }
  };

  const handleToggleActive = async (category) => {
    if (category.is_active && makerCheckerOn) {
      setConfirmDeactivate(category);
      return;
    }
    try {
      const res = await categoriesAPI.update(category.id, {
        name: category.name,
        description: category.description || '',
        parent: category.parent,
        is_active: !category.is_active,
      });
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else {
        toast.success(
          `Category ${!category.is_active ? 'activated' : 'deactivated'} successfully`
        );
      }
      loadCategories();
    } catch {
      toast.error('Failed to update category');
    }
  };

  const confirmDeactivateAction = async () => {
    if (!confirmDeactivate) return;
    if (!deactivateReason.trim()) {
      toast.warning('Enter a reason for deactivating this category.');
      return;
    }
    try {
      const cat = confirmDeactivate;
      const res = await categoriesAPI.update(cat.id, {
        name: cat.name,
        description: cat.description || '',
        parent: cat.parent,
        is_active: false,
        reason: deactivateReason.trim(),
      });
      if (isPendingApprovalResponse(res.status)) {
        toast.warning(PENDING_APPROVAL_MESSAGE);
      } else {
        toast.success('Category deactivated');
      }
      loadCategories();
    } catch {
      toast.error('Failed to deactivate category');
    } finally {
      setConfirmDeactivate(null);
      setDeactivateReason('');
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
              ? 'Try a different search term, set filter to All or Inactive, or check level filter.'
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
                    <PendingApprovalBadges pendingApproval={category.pending_approval} />
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
        message={
          makerCheckerOn
            ? 'Submit a delete proposal for checker approval. The category stays until approved.'
            : 'Products linked to this category may be cleared. Subcategories under a parent must be deleted or moved first. This cannot be undone.'
        }
        onConfirm={confirmDeleteAction}
        onCancel={() => {
          setConfirmDelete(null);
          setDeleteReason('');
        }}
        confirmText={makerCheckerOn ? 'Submit for approval' : 'Delete'}
        cancelText="Cancel"
        type="danger"
      >
        {makerCheckerOn && confirmDelete ? (
          <ChangeReasonField context="catalog" value={deleteReason} onChange={setDeleteReason} />
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        isOpen={!!confirmDeactivate}
        title="Deactivate category"
        message="Submit deactivation for checker approval. The category stays active in pickers until approved."
        onConfirm={confirmDeactivateAction}
        onCancel={() => {
          setConfirmDeactivate(null);
          setDeactivateReason('');
        }}
        confirmText="Submit for approval"
        cancelText="Cancel"
        type="warning"
      >
        {confirmDeactivate ? (
          <ChangeReasonField
            context="catalog"
            value={deactivateReason}
            onChange={setDeactivateReason}
          />
        ) : null}
      </ConfirmDialog>
    </PageShell>
  );
};

export default Categories;
