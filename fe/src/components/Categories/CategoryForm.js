import React, { useState, useEffect } from 'react';
import { categoriesAPI } from '../../services/api';
import SearchableSelect from '../Shared/SearchableSelect';
import './Categories.css';

const CategoryForm = ({ category, onClose, onSave, categories = [] }) => {
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
    
    // Clear error for this field
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
      
      // Only include parent if it's selected
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

  // Filter out current category from parent options (to prevent circular references)
  const parentOptions = categories.filter(cat => !category || cat.id !== category.id);

  return (
    <div className="modal-overlay">
      <div className="modal-content category-form-modal">
        <div className="modal-header">
          <h2>{category ? 'Edit Category' : 'Add Category'}</h2>
          <button onClick={onClose} className="close-btn">×</button>
        </div>

        <form onSubmit={handleSubmit} className="category-form">
          {error && <div className="error-message">{error}</div>}

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
            <small>Select a parent category to create a subcategory</small>
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
              />
              <span>Active</span>
            </label>
            <small>Inactive categories won't appear in product selection</small>
          </div>

          <div className="form-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={loading}>
              {loading ? 'Saving...' : category ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CategoryForm;

