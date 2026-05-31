import React, { useState, useEffect } from 'react';
import { categoriesAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';

const CategoryForm = ({ category, onClose, onSave, categories = [], hideStatusToggles = false }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    parent: '',
    is_active: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (category) {
      setFormData({
        name: category.name || '',
        description: category.description || '',
        parent: category.parent || '',
        is_active: category.is_active !== undefined ? category.is_active : true,
      });
    }
  }, [category]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));

    if (error) {
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.name.trim()) {
      setError('Category name is required');
      return;
    }

    setLoading(true);
    try {
      const submitData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        is_active: formData.is_active,
      };

      if (formData.parent) {
        submitData.parent = parseInt(formData.parent);
      }

      if (category) {
        await categoriesAPI.update(category.id, submitData);
      } else {
        await categoriesAPI.create(submitData);
      }

      onSave();
    } catch (error) {
      const errorMsg = error.response?.data?.error ||
                      error.response?.data?.name?.[0] ||
                      error.response?.data?.detail ||
                      'Failed to save category';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const parentOptions = categories.filter(cat => !category || cat.id !== category.id);

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{category ? 'Edit Category' : 'Add Category'}</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="category-form">
            {error && (
              <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="form-group">
              <label>Category Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                placeholder="Enter category name"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows="4"
                placeholder="Enter category description (optional)"
              />
            </div>

            <div className="form-group">
              <label>Parent Category</label>
              <SearchableSelect
                name="parent"
                value={formData.parent}
                onChange={handleChange}
                options={[
                  { id: '', name: 'No Parent (Top Level)' },
                  ...parentOptions
                    .filter(cat => cat.is_active !== false)
                    .map(cat => ({ id: cat.id, name: cat.name }))
                ]}
                placeholder="No Parent (Top Level)"
              />
              <small className="form-text text-muted">Select a parent category to create a subcategory</small>
            </div>

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
                <small className="form-text text-muted">Inactive categories won&apos;t appear in product selection</small>
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
