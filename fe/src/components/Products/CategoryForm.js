import React, { useState, useEffect } from 'react';
import { categoriesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import '../../styles/slide-in-panel.css';
import './Products.css';

const CategoryForm = ({ 
  isOpen, 
  onClose, 
  onSave, 
  parentCategory = null,
  categories = [] // For selecting parent when creating subcategory
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    parent: parentCategory ? String(parentCategory) : '',
    is_active: true,
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (isOpen) {
      // Reset form when opening
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
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validate = () => {
    const newErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Category name is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }

    setLoading(true);
    try {
      const submitData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        is_active: formData.is_active,
      };

      // Include parent if provided (for subcategories) or if parentCategory prop is set
      if (parentCategory) {
        submitData.parent = parseInt(parentCategory);
      } else if (formData.parent) {
        submitData.parent = parseInt(formData.parent);
      }

      const response = await categoriesAPI.create(submitData);
      toast.success(parentCategory ? 'Subcategory created successfully' : 'Category created successfully');
      
      // Call onSave with the new category
      if (onSave) {
        onSave(response.data);
      }
      
      // Close the form
      onClose();
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage = error.response.data.error || 
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

  // Get parent categories (categories without a parent)
  const parentCategories = categories.filter(cat => !cat.parent);

  return (
    <div className="slide-in-overlay nested" onClick={onClose}>
      <div className="slide-in-panel nested" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{parentCategory ? 'Add New Subcategory' : 'Add New Category'}</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="category-form">
            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
                placeholder={parentCategory ? 'Subcategory name' : 'Category name'}
              />
              {errors.name && <span className="error">{errors.name}</span>}
            </div>

            {!parentCategory && (
              <div className="form-group">
                <label>Parent Category (optional)</label>
                <select
                  name="parent"
                  value={formData.parent}
                  onChange={handleChange}
                >
                  <option value="">None (Top-level category)</option>
                  {parentCategories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
                <small className="form-text text-muted">
                  Leave empty to create a top-level category, or select a parent to create a subcategory
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
              <label>
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleChange}
                />
                {' '}Active
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
            {loading ? 'Creating...' : 'Create Category'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CategoryForm;
