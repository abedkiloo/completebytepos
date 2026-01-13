import React, { useState } from 'react';
import { categoriesAPI } from '../../services/api';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import './Products.css';

const CategoryManager = ({ categories = [], onClose, onUpdate }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [formData, setFormData] = useState({ name: '', description: '', is_active: true });
  const [loading, setLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (editingCategory) {
        await categoriesAPI.update(editingCategory.id, formData);
      } else {
        await categoriesAPI.create(formData);
      }
      setShowForm(false);
      setEditingCategory(null);
      setFormData({ name: '', description: '', is_active: true });
      onUpdate();
      toast.success(editingCategory ? 'Category updated successfully' : 'Category created successfully');
    } catch (error) {
      toast.error('Failed to save category: ' + (error.response?.data?.error || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = (id) => {
    setConfirmDelete(id);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;

    try {
      await categoriesAPI.delete(confirmDelete);
      onUpdate();
      toast.success('Category deleted successfully');
    } catch (error) {
      toast.error('Failed to delete category: ' + (error.response?.data?.error || error.message));
    } finally {
      setConfirmDelete(null);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content category-modal">
        <div className="modal-header">
          <h2>Manage Categories</h2>
          <button onClick={onClose} className="close-btn">×</button>
        </div>

        <div className="category-manager">
          <button onClick={() => { setEditingCategory(null); setFormData({ name: '', description: '', is_active: true }); setShowForm(true); }}>
            + Add Category
          </button>

          {showForm && (
            <form onSubmit={handleSubmit} className="category-form">
              <input
                type="text"
                placeholder="Category name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
              <textarea
                placeholder="Description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
              <label>
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                Active
              </label>
              <div className="form-actions">
                <button type="button" onClick={() => { setShowForm(false); setEditingCategory(null); }}>
                  Cancel
                </button>
                <button type="submit" disabled={loading}>
                  {editingCategory ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          )}

          <div className="categories-list">
            {Array.isArray(categories) && categories.map(category => (
              <div key={category.id} className="category-item">
                <div className="category-info">
                  <h3>{category.name}</h3>
                  {category.description && <p>{category.description}</p>}
                  <span className="product-count">{category.product_count || 0} products</span>
                </div>
                <div className="category-actions">
                  <button
                    onClick={() => {
                      setEditingCategory(category);
                      setFormData({
                        name: category.name,
                        description: category.description || '',
                        is_active: category.is_active !== undefined ? category.is_active : true
                      });
                      setShowForm(true);
                    }}
                  >
                    Edit
                  </button>
                  <button onClick={() => handleDelete(category.id)} className="danger">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CategoryManager;

