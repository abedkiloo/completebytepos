import React, { useState, useEffect } from 'react';
import { categoriesAPI } from '../../services/api';
import { formatNumber } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import CategoryForm from './CategoryForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { toast } from '../../utils/toast';
import '../../styles/shared.css';
import './Categories.css';

const Categories = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterActive, setFilterActive] = useState('all'); // all, active, inactive
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

  const handleDelete = (id) => {
    setConfirmDelete(id);
  };

  const confirmDeleteAction = async () => {
    if (!confirmDelete) return;

    try {
      await categoriesAPI.delete(confirmDelete);
      loadCategories();
      toast.success('Category deleted successfully');
    } catch (error) {
      const errorMsg = error.response?.data?.error || error.response?.data?.detail || 'Failed to delete category';
      toast.error(errorMsg);
    } finally {
      setConfirmDelete(null);
    }
  };

  const handleToggleActive = async (category) => {
    try {
      await categoriesAPI.update(category.id, {
        ...category,
        is_active: !category.is_active
      });
      loadCategories();
      toast.success(`Category ${!category.is_active ? 'activated' : 'deactivated'} successfully`);
    } catch (error) {
      toast.error('Failed to update category');
    }
  };

  const filteredCategories = categories.filter(cat => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return cat.name.toLowerCase().includes(query) ||
             (cat.description && cat.description.toLowerCase().includes(query));
    }
    return true;
  });

  return (
    <Layout>
      <div className="categories-page">
      <div className="page-header">
        <div className="page-header-content">
          <h1>Category Management</h1>
        </div>
        <div className="page-header-actions">
          <button
            onClick={() => {
              setEditingCategory(null);
              setShowForm(true);
            }}
            className="btn btn-primary"
          >
            <span>+</span>
            <span>Add Category</span>
          </button>
        </div>
      </div>

      <div className="categories-filters">
        <input
          type="text"
          placeholder="Search categories..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <div className="filter-buttons">
          <button
            className={filterActive === 'all' ? 'active' : ''}
            onClick={() => setFilterActive('all')}
          >
            All
          </button>
          <button
            className={filterActive === 'active' ? 'active' : ''}
            onClick={() => setFilterActive('active')}
          >
            Active
          </button>
          <button
            className={filterActive === 'inactive' ? 'active' : ''}
            onClick={() => setFilterActive('inactive')}
          >
            Inactive
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading categories...</div>
      ) : (
        <div className="categories-grid">
          {filteredCategories.length === 0 ? (
            <div className="empty-state">
              {searchQuery ? 'No categories found matching your search' : 'No categories found'}
            </div>
          ) : (
            filteredCategories.map(category => (
              <div key={category.id} className={`category-card ${!category.is_active ? 'inactive' : ''}`}>
                <div className="category-header">
                  <h3>{category.name}</h3>
                  <span className={`status-badge ${category.is_active ? 'active' : 'inactive'}`}>
                    {category.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                
                {category.description && (
                  <div className="category-description">
                    <p>{category.description}</p>
                  </div>
                )}

                <div className="category-stats">
                  <div className="stat-item">
                    <span className="stat-label">Products:</span>
                    <span className="stat-value">{formatNumber(category.product_count || 0)}</span>
                  </div>
                  {category.children_count > 0 && (
                    <div className="stat-item">
                      <span className="stat-label">Subcategories:</span>
                      <span className="stat-value">{formatNumber(category.children_count || 0)}</span>
                    </div>
                  )}
                </div>

                <div className="category-actions">
                  <button
                    onClick={() => {
                      setEditingCategory(category);
                      setShowForm(true);
                    }}
                    className="btn-edit"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleToggleActive(category)}
                    className={category.is_active ? 'btn-deactivate' : 'btn-activate'}
                  >
                    {category.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    onClick={() => handleDelete(category.id)}
                    className="btn-delete"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
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

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        isOpen={!!confirmDelete}
        title="Delete Category"
        message="Are you sure you want to delete this category? Products in this category will have their category set to null."
        onConfirm={confirmDeleteAction}
        onCancel={() => setConfirmDelete(null)}
        confirmText="Delete"
        cancelText="Cancel"
        type="danger"
      />
      </div>
    </Layout>
  );
};

export default Categories;

