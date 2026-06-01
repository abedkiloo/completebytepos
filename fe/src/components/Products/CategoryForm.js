import React, { useState, useEffect, useMemo } from 'react';
import { categoriesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';

const CategoryForm = ({
  isOpen,
  onClose,
  onSave,
  parentCategory = null,
  categories = [],
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    parent: parentCategory ? String(parentCategory) : '',
    is_active: true,
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const isSubcategory = Boolean(parentCategory);
  const topLevelParents = useMemo(
    () => categories.filter((cat) => !cat.parent),
    [categories]
  );
  const parentName = useMemo(() => {
    if (!parentCategory) return '';
    const found = categories.find((c) => String(c.id) === String(parentCategory));
    return found?.name || '';
  }, [categories, parentCategory]);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        description: '',
        parent: parentCategory ? String(parentCategory) : '',
        is_active: true,
      });
      setErrors({});
    }
  }, [isOpen, parentCategory]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      const submitData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        is_active: formData.is_active,
      };

      if (parentCategory) {
        submitData.parent = parseInt(parentCategory, 10);
      } else if (formData.parent) {
        submitData.parent = parseInt(formData.parent, 10);
      }

      const response = await categoriesAPI.create(submitData);
      toast.success(
        isSubcategory ? 'Subcategory created successfully' : 'Category created successfully'
      );
      if (onSave) onSave(response.data);
      onClose();
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage =
          error.response.data.error ||
          error.response.data.parent?.[0] ||
          Object.values(error.response.data).flat().join(', ') ||
          'Failed to create category';
        toast.error(errorMessage);
      } else {
        toast.error('Failed to create category: ' + (error.message || 'Unknown error'));
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="slide-in-overlay nested" onClick={onClose}>
      <div className="slide-in-panel nested" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{isSubcategory ? 'Add subcategory' : 'Add category'}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="category-form">
            {isSubcategory && (
              <div className="form-group">
                <label>Parent category</label>
                <input type="text" value={parentName} readOnly className="readonly bg-muted" />
              </div>
            )}

            <div className="form-group">
              <label>{isSubcategory ? 'Subcategory name *' : 'Category name *'}</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                placeholder={isSubcategory ? 'Subcategory name' : 'Category name'}
                autoFocus
              />
              {errors.name && <span className="error">{errors.name}</span>}
            </div>

            {!isSubcategory && (
              <div className="form-group">
                <label>Parent (optional)</label>
                <SearchableSelect
                  name="parent"
                  value={formData.parent || ''}
                  onChange={handleChange}
                  options={[
                    { id: '', name: 'None — top-level category' },
                    ...topLevelParents.map((cat) => ({ id: cat.id, name: cat.name })),
                  ]}
                  placeholder="Top-level parent only"
                  searchable={true}
                />
                <small className="form-text text-muted">
                  Pick a parent only to create a subcategory under an existing category.
                </small>
              </div>
            )}

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
            </div>
          </form>
        </div>

        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? 'Creating…' : isSubcategory ? 'Create subcategory' : 'Create category'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CategoryForm;
