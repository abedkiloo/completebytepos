import React, { useState, useEffect } from 'react';
import { productsAPI, categoriesAPI, sizesAPI, colorsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import '../../styles/slide-in-panel.css';
import './Products.css';

const ProductForm = ({ product, categories = [], onClose, onSave }) => {
  const [formData, setFormData] = useState({
    name: '',
    sku: '',
    barcode: '',
    category: '',
    subcategory: '',
    has_variants: false,
    available_sizes: [],
    available_colors: [],
    price: '',
    cost: '',
    stock_quantity: 0,
    low_stock_threshold: 10,
    reorder_quantity: 50,
    unit: 'piece',
    description: '',
    supplier: '',
    supplier_contact: '',
    tax_rate: 0,
    is_taxable: true,
    track_stock: true,
    is_active: true,
  });
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [subcategories, setSubcategories] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [colors, setColors] = useState([]);

  useEffect(() => {
    // Load sizes and colors
    const loadSizesAndColors = async () => {
      try {
        const [sizesRes, colorsRes] = await Promise.all([
          sizesAPI.list({ is_active: 'true' }),
          colorsAPI.list({ is_active: 'true' })
        ]);
        setSizes(sizesRes.data.results || sizesRes.data || []);
        setColors(colorsRes.data.results || colorsRes.data || []);
      } catch (error) {
        console.error('Error loading sizes/colors:', error);
      }
    };
    loadSizesAndColors();
  }, []);

  useEffect(() => {
    // Load subcategories when category changes
    const loadSubcategories = async () => {
      if (formData.category) {
        try {
          const response = await categoriesAPI.list({ parent: formData.category, is_active: 'true' });
          const newSubcategories = response.data.results || response.data || [];
          setSubcategories(newSubcategories);
          
          // Clear subcategory if current one is not in the new list
          if (formData.subcategory) {
            const subcategoryExists = newSubcategories.some(sub => sub.id === parseInt(formData.subcategory));
            if (!subcategoryExists) {
              setFormData(prev => ({ ...prev, subcategory: '' }));
            }
          }
        } catch (error) {
          console.error('Error loading subcategories:', error);
          setSubcategories([]);
          setFormData(prev => ({ ...prev, subcategory: '' }));
        }
      } else {
        setSubcategories([]);
        setFormData(prev => ({ ...prev, subcategory: '' }));
      }
    };
    loadSubcategories();
  }, [formData.category]);

  useEffect(() => {
    if (product) {
      // Extract size and color IDs, ensuring they're numbers
      const sizeIds = product.available_sizes_detail 
        ? product.available_sizes_detail.map(s => Number(s.id)).filter(id => !isNaN(id))
        : (Array.isArray(product.available_sizes) ? product.available_sizes : []).map(id => Number(id)).filter(id => !isNaN(id));
      
      const colorIds = product.available_colors_detail
        ? product.available_colors_detail.map(c => Number(c.id)).filter(id => !isNaN(id))
        : (Array.isArray(product.available_colors) ? product.available_colors : []).map(id => Number(id)).filter(id => !isNaN(id));

      setFormData(prev => ({
        ...prev,
        name: product.name || '',
        sku: product.sku || '',
        barcode: product.barcode || '',
        category: product.category ? String(product.category) : '',
        subcategory: product.subcategory ? String(product.subcategory) : '',
        has_variants: product.has_variants || false,
        available_sizes: sizeIds,
        available_colors: colorIds,
        price: product.price || '',
        cost: product.cost || '',
        stock_quantity: product.stock_quantity || 0,
        low_stock_threshold: product.low_stock_threshold || 10,
        reorder_quantity: product.reorder_quantity || 50,
        unit: product.unit || 'piece',
        description: product.description || '',
        supplier: product.supplier || '',
        supplier_contact: product.supplier_contact || '',
        tax_rate: product.tax_rate || 0,
        is_taxable: product.is_taxable !== undefined ? product.is_taxable : true,
        track_stock: product.track_stock !== undefined ? product.track_stock : true,
        is_active: product.is_active !== undefined ? product.is_active : true,
      }));
      if (product.image_url) {
        setImagePreview(product.image_url);
      }
    }
  }, [product]);

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

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const validate = () => {
    const newErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Product name is required';
    }
    
    if (!formData.price || parseFloat(formData.price) < 0) {
      newErrors.price = 'Valid price is required';
    }
    
    if (formData.cost && parseFloat(formData.cost) < 0) {
      newErrors.cost = 'Cost must be positive';
    }
    
    if (parseFloat(formData.price) < parseFloat(formData.cost || 0)) {
      newErrors.price = 'Price should be greater than or equal to cost';
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
      const submitData = new FormData();
      
      Object.keys(formData).forEach(key => {
        if (key === 'available_sizes' || key === 'available_colors') {
          // Handle array fields
          formData[key].forEach(id => {
            submitData.append(key, id);
          });
        } else if (formData[key] !== '' && formData[key] !== null && formData[key] !== undefined) {
          submitData.append(key, formData[key]);
        }
      });
      
      if (image) {
        submitData.append('image', image);
      }

      let response;
      if (product) {
        response = await productsAPI.update(product.id, submitData);
        console.log('Product updated:', response.data);
        toast.success('Product updated successfully');
      } else {
        response = await productsAPI.create(submitData);
        console.log('Product created:', response.data);
        toast.success('Product created successfully');
      }
      
      // Wait a bit for backend to process, then save and refresh
      setTimeout(() => {
        onSave();
      }, 200);
    } catch (error) {
      if (error.response?.data) {
        setErrors(error.response.data);
        const errorMessage = error.response.data.error || 
          Object.values(error.response.data).flat().join(', ') || 
          'Failed to save product';
        toast.error(errorMessage);
      } else {
        toast.error('Failed to save product: ' + (error.message || 'Unknown error'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{product ? 'Edit Product' : 'Add Product'}</h2>
          <button onClick={onClose} className="slide-in-panel-close">×</button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="product-form">
          <div className="form-row">
            <div className="form-group">
              <label>Product Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleChange}
                required
              />
              {errors.name && <span className="error">{errors.name}</span>}
            </div>

            <div className="form-group">
              <label>SKU</label>
              <input
                type="text"
                name="sku"
                value={formData.sku}
                onChange={handleChange}
                placeholder="Auto-generated if empty"
              />
              {errors.sku && <span className="error">{errors.sku}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Barcode</label>
              <input
                type="text"
                name="barcode"
                value={formData.barcode}
                onChange={handleChange}
              />
              {errors.barcode && <span className="error">{errors.barcode}</span>}
            </div>

            <div className="form-group">
              <label>Category</label>
              <select
                name="category"
                value={formData.category}
                onChange={handleChange}
              >
                <option value="">No Category</option>
                {Array.isArray(categories) && categories
                  .filter(cat => !cat.parent) // Only show parent categories
                  .map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
              </select>
            </div>

            <div className="form-group">
              <label>Subcategory</label>
              <select
                name="subcategory"
                value={formData.subcategory}
                onChange={handleChange}
                disabled={!formData.category}
              >
                <option value="">No Subcategory</option>
                {subcategories.map(subcat => (
                  <option key={subcat.id} value={subcat.id}>{subcat.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  name="has_variants"
                  checked={formData.has_variants}
                  onChange={handleChange}
                />
                {' '}This product has size/color variants
              </label>
            </div>
          </div>

          {formData.has_variants && (
            <div className="form-row">
              <div className="form-group">
                <label>Available Sizes</label>
                <select
                  name="available_sizes"
                  multiple
                  value={Array.isArray(formData.available_sizes) ? formData.available_sizes.map(id => String(id)) : []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                    setFormData(prev => ({ ...prev, available_sizes: selected }));
                  }}
                  style={{ minHeight: '100px' }}
                >
                  {sizes.map(size => (
                    <option key={size.id} value={String(size.id)}>{size.name} ({size.code})</option>
                  ))}
                </select>
                <small>
                  {Array.isArray(formData.available_sizes) && formData.available_sizes.length > 0 
                    ? `Selected: ${formData.available_sizes.map(id => {
                        const size = sizes.find(s => s.id === id);
                        return size ? size.name : '';
                      }).filter(Boolean).join(', ')}`
                    : 'Hold Ctrl/Cmd to select multiple sizes'}
                </small>
              </div>

              <div className="form-group">
                <label>Available Colors</label>
                <select
                  name="available_colors"
                  multiple
                  value={Array.isArray(formData.available_colors) ? formData.available_colors.map(id => String(id)) : []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                    setFormData(prev => ({ ...prev, available_colors: selected }));
                  }}
                  style={{ minHeight: '100px' }}
                >
                  {colors.map(color => (
                    <option key={color.id} value={String(color.id)}>
                      {color.name}{color.hex_code ? ` (${color.hex_code})` : ''}
                    </option>
                  ))}
                </select>
                <small>
                  {Array.isArray(formData.available_colors) && formData.available_colors.length > 0 
                    ? `Selected: ${formData.available_colors.map(id => {
                        const color = colors.find(c => c.id === id);
                        return color ? color.name : '';
                      }).filter(Boolean).join(', ')}`
                    : 'Hold Ctrl/Cmd to select multiple colors'}
                </small>
              </div>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Price (KES) *</label>
              <input
                type="number"
                name="price"
                value={formData.price}
                onChange={handleChange}
                step="0.01"
                min="0"
                required
              />
              {errors.price && <span className="error">{errors.price}</span>}
            </div>

            <div className="form-group">
              <label>Cost (KES)</label>
              <input
                type="number"
                name="cost"
                value={formData.cost}
                onChange={handleChange}
                step="0.01"
                min="0"
              />
              {errors.cost && <span className="error">{errors.cost}</span>}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Stock Quantity</label>
              <input
                type="number"
                name="stock_quantity"
                value={formData.stock_quantity}
                onChange={handleChange}
                min="0"
              />
            </div>

            <div className="form-group">
              <label>Low Stock Threshold</label>
              <input
                type="number"
                name="low_stock_threshold"
                value={formData.low_stock_threshold}
                onChange={handleChange}
                min="0"
              />
            </div>

            <div className="form-group">
              <label>Reorder Quantity</label>
              <input
                type="number"
                name="reorder_quantity"
                value={formData.reorder_quantity}
                onChange={handleChange}
                min="0"
              />
            </div>

            <div className="form-group">
              <label>Unit</label>
              <select
                name="unit"
                value={formData.unit}
                onChange={handleChange}
              >
                <option value="piece">Piece</option>
                <option value="kg">Kilogram</option>
                <option value="g">Gram</option>
                <option value="l">Liter</option>
                <option value="ml">Milliliter</option>
                <option value="box">Box</option>
                <option value="pack">Pack</option>
                <option value="bottle">Bottle</option>
                <option value="can">Can</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Supplier</label>
              <input
                type="text"
                name="supplier"
                value={formData.supplier}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label>Supplier Contact</label>
              <input
                type="text"
                name="supplier_contact"
                value={formData.supplier_contact}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Tax Rate (%)</label>
              <input
                type="number"
                name="tax_rate"
                value={formData.tax_rate}
                onChange={handleChange}
                step="0.01"
                min="0"
              />
            </div>

            <div className="form-group">
              <label>Image</label>
              <input
                type="file"
                accept="image/*"
                onChange={handleImageChange}
              />
              {imagePreview && (
                <img src={imagePreview} alt="Preview" className="image-preview" />
              )}
            </div>
          </div>

          <div className="form-group">
            <label>Description</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
            />
          </div>

          <div className="form-checkboxes">
            <label>
              <input
                type="checkbox"
                name="track_stock"
                checked={formData.track_stock}
                onChange={handleChange}
              />
              Track Stock
            </label>
            <label>
              <input
                type="checkbox"
                name="is_taxable"
                checked={formData.is_taxable}
                onChange={handleChange}
              />
              Taxable
            </label>
            <label>
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
              />
              Active
            </label>
          </div>

          </form>
        </div>
        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading ? 'Saving...' : product ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProductForm;

