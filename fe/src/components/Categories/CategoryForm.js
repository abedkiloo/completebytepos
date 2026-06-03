import React, { useState, useEffect, useMemo } from 'react';
import { categoriesAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import { required, normalizeApiErrors } from '../../utils/formValidation';

const CategoryForm = ({
  category,
  initialParentId = null,
  onClose,
  onSave,
  categories = [],
  hideStatusToggles = false,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    parent: '',
    is_active: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isSubcategory = Boolean(category?.parent);
  const hasChildren = (category?.children_count || 0) > 0;
  const lockedParentId =
    initialParentId != null
      ? String(initialParentId)
      : isSubcategory
        ? String(category.parent)
        : '';

  const topLevelParents = useMemo(
    () =>
      categories.filter(
        (cat) => !cat.parent && (!category || cat.id !== category.id)
      ),
    [categories, category]
  );

  const lockedParentName = useMemo(() => {
    if (!lockedParentId) return '';
    const found = categories.find((c) => String(c.id) === lockedParentId);
    return found?.name || '';
  }, [categories, lockedParentId]);

  useEffect(() => {
    if (category) {
      setFormData({
        name: category.name || '',
        description: category.description || '',
        parent: category.parent ? String(category.parent) : '',
        is_active: category.is_active !== undefined ? category.is_active : true,
      });
    } else {
      setFormData({
        name: '',
        description: '',
        parent: initialParentId != null ? String(initialParentId) : '',
        is_active: true,
      });
    }
    setError('');
  }, [category, initialParentId]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const nameErr = required(formData.name, 'Category name is required');
    if (nameErr) {
      setError(nameErr);
      return;
    }

    setError('');
    setLoading(true);
    try {
      const submitData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        is_active: formData.is_active,
      };

      const parentToUse = lockedParentId || formData.parent;
      if (parentToUse) {
        submitData.parent = parseInt(parentToUse, 10);
      } else if (category && category.parent) {
        submitData.parent = null;
      }

      if (category) {
        await categoriesAPI.update(category.id, submitData);
      } else {
        await categoriesAPI.create(submitData);
      }

      onSave();
    } catch (err) {
      const apiErrors = normalizeApiErrors(err.response?.data);
      const fieldMsg =
        apiErrors.name || apiErrors.parent || apiErrors._form;
      setError(fieldMsg || 'Failed to save category');
    } finally {
      setLoading(false);
    }
  };

  const showParentPicker =
    !lockedParentId && !hasChildren && !isSubcategory;

  const title = category
    ? isSubcategory
      ? 'Edit subcategory'
      : 'Edit category'
    : lockedParentId
      ? 'Add subcategory'
      : 'Add category';

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{title}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="category-form">
            {lockedParentId && (
              <div className="form-group">
                <label>Parent category</label>
                <input
                  type="text"
                  value={lockedParentName}
                  readOnly
                  className="readonly bg-muted"
                />
                <small className="form-text text-muted">
                  Subcategories belong to one top-level category.
                </small>
              </div>
            )}

            <div className={`form-group ${error && !lockedParentId ? 'has-error field-error' : ''}`}>
              <label>{lockedParentId ? 'Subcategory name *' : 'Category name *'}</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                placeholder={lockedParentId ? 'e.g. Leather sofas' : 'e.g. Furniture'}
                autoFocus
                aria-invalid={Boolean(error)}
              />
              {error && (
                <span className="field-error-message" role="alert">
                  {error}
                </span>
              )}
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows="3"
                placeholder="Optional description"
              />
            </div>

            {showParentPicker && (
              <div className="form-group">
                <label>Parent category (optional)</label>
                <SearchableSelect
                  name="parent"
                  value={formData.parent || ''}
                  onChange={handleChange}
                  options={[
                    { id: '', name: 'None — top-level category' },
                    ...topLevelParents
                      .filter((cat) => cat.is_active !== false)
                      .map((cat) => ({ id: cat.id, name: cat.name })),
                  ]}
                  placeholder="Top-level category only"
                />
                <small className="form-text text-muted">
                  Only top-level categories can be parents. You cannot nest subcategories
                  under other subcategories.
                </small>
              </div>
            )}

            {hasChildren && !isSubcategory && (
              <p className="text-sm text-muted-foreground">
                This category has subcategories. Its parent cannot be changed.
              </p>
            )}

            {!hideStatusToggles && (
              <div className="form-group">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    name="is_active"
                    checked={formData.is_active}
                    onChange={handleChange}
                  />
                  <span>Active</span>
                </label>
                <small className="form-text text-muted">
                  Inactive categories are hidden from product and POS pickers.
                </small>
              </div>
            )}
          </form>
        </div>

        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? 'Saving...' : category ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CategoryForm;
