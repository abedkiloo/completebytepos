import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { productsAPI, categoriesAPI, sizesAPI, colorsAPI, suppliersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { resolveMediaUrl } from '../../utils/mediaUrl';
import { useProductVariantsEnabled } from '../../hooks/useProductVariantsEnabled';
import SearchableSelect from '../Shared/SearchableSelect';
import CategoryForm from './CategoryForm';
import SupplierForm from '../Suppliers/SupplierForm';
import {
  SELLING_PRICE_CLASS,
  productImagesEnabled,
} from '../../utils/productDisplay';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useProductUnits } from '../../hooks/useProductUnits';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import ProductVariantsPanel from './ProductVariantsPanel';
import {
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  productEditNeedsReason,
  PENDING_APPROVAL_MESSAGE,
} from '../../utils/makerChecker';

const defaultFieldAccess = (catalogOnly, financialFieldsLocked) => ({
  catalog: true,
  pricing: !catalogOnly && !financialFieldsLocked,
  cost: !catalogOnly && !financialFieldsLocked,
  stock: !catalogOnly && !financialFieldsLocked,
  catalogOnly,
});

const ProductForm = ({
  product,
  categories = [],
  onClose,
  onSave,
  catalogOnly = false,
  fieldAccess: fieldAccessProp = null,
  financialFieldsLocked = false,
  showProductStatus = true,
  showCost = true,
  showMrp = true,
}) => {
  const imagesEnabled = productImagesEnabled();
  const variantsEnabled = useProductVariantsEnabled();
  const { settings: storeSettings } = useStoreSettings();
  const { options: unitOptions } = useProductUnits();
  const makerCheckerOn = isMakerCheckerEnabled(storeSettings);
  const fieldAccess =
    fieldAccessProp ?? defaultFieldAccess(catalogOnly, financialFieldsLocked);
  const showPricingFields = fieldAccess.pricing;
  const showCostField = fieldAccess.cost && showCost;
  const showStockFields = fieldAccess.stock;
  const makerCheckerFinancialLocked =
    !fieldAccess.pricing && !fieldAccess.cost && !fieldAccess.stock;
  const [changeReason, setChangeReason] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    sku: '',
    barcode: '',
    category: '',
    subcategory: '',
    has_variants: false,
    available_sizes: [],
    available_colors: [],
    mrp: '',
    selling_price: '',
    cost: '',
    stock_quantity: 0,
    low_stock_threshold: 10,
    reorder_quantity: 50,
    unit: 'piece',
    description: '',
    supplier: '',
    supplier_name: '',
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
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [showSubcategoryForm, setShowSubcategoryForm] = useState(false);
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [allCategories, setAllCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [sizeSearch, setSizeSearch] = useState('');
  const [colorSearch, setColorSearch] = useState('');

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
    // Load all categories for the searchable dropdown
    const loadAllCategories = async () => {
      try {
        const response = await categoriesAPI.list({ is_active: 'true' });
        const categoriesData = response.data.results || response.data || [];
        setAllCategories(Array.isArray(categoriesData) ? categoriesData : []);
      } catch (error) {
        console.error('Error loading categories:', error);
      }
    };
    loadAllCategories();
  }, []);

  useEffect(() => {
    // Load suppliers for the searchable dropdown
    const loadSuppliers = async () => {
      try {
        const response = await suppliersAPI.list({ is_active: 'true' });
        const suppliersData = response.data.results || response.data || [];
        setSuppliers(Array.isArray(suppliersData) ? suppliersData : []);
      } catch (error) {
        console.error('Error loading suppliers:', error);
        // If suppliers module is disabled, just set empty array
        setSuppliers([]);
      }
    };
    loadSuppliers();
  }, []);

  useEffect(() => {
    // Load subcategories when category changes - filter by parent category
    const loadSubcategories = async () => {
      if (formData.category) {
        try {
          // Clear subcategories first to show loading state
          setSubcategories([]);
          
          // Ensure category ID is a number for the API call
          const categoryId = parseInt(formData.category);
          if (isNaN(categoryId)) {
            console.error('Invalid category ID:', formData.category);
            setSubcategories([]);
            return;
          }
          
          const response = await categoriesAPI.list({ parent: categoryId, is_active: 'true' });
          const newSubcategories = response.data.results || response.data || [];
          const validSubcategories = Array.isArray(newSubcategories) ? newSubcategories : [];
          setSubcategories(validSubcategories);
          
          // Clear subcategory if current one is not in the new list (category changed)
          if (formData.subcategory) {
            const subcategoryId = parseInt(formData.subcategory);
            const subcategoryExists = validSubcategories.some(sub => sub.id === subcategoryId);
            if (!subcategoryExists) {
              setFormData(prev => ({ ...prev, subcategory: '' }));
            }
          }
        } catch (error) {
          console.error('Error loading subcategories:', error);
          setSubcategories([]);
          // Only clear subcategory if category was actually changed (not on initial load)
          if (formData.subcategory) {
            setFormData(prev => ({ ...prev, subcategory: '' }));
          }
        }
      } else {
        setSubcategories([]);
        if (formData.subcategory) {
          setFormData((prev) => ({ ...prev, subcategory: '' }));
        }
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
        mrp: product.mrp ?? product.price ?? '',
        selling_price: product.selling_price ?? product.price ?? '',
        cost: product.cost || '',
        stock_quantity: product.stock_quantity || 0,
        low_stock_threshold: product.low_stock_threshold || 10,
        reorder_quantity: product.reorder_quantity || 50,
        unit: product.unit || 'piece',
        description: product.description || '',
        supplier: product.supplier ? String(product.supplier) : (product.supplier_detail?.id ? String(product.supplier_detail.id) : ''),
        supplier_name: product.supplier_name || product.supplier_name_display || (product.supplier_detail?.name || ''),
        supplier_contact: product.supplier_contact || '',
        tax_rate: product.tax_rate || 0,
        is_taxable: product.is_taxable !== undefined ? product.is_taxable : true,
        track_stock: product.track_stock !== undefined ? product.track_stock : true,
        is_active: product.is_active !== undefined ? product.is_active : true,
      }));
      if (product.image_url) {
        setImagePreview(resolveMediaUrl(product.image_url));
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

  const handleCategoryCreated = (newCategory) => {
    // Reload all categories
    const loadAllCategories = async () => {
      try {
        const response = await categoriesAPI.list({ is_active: 'true' });
        const categoriesData = response.data.results || response.data || [];
        const updatedCategories = Array.isArray(categoriesData) ? categoriesData : [];
        setAllCategories(updatedCategories);
        
        // If it's a parent category, select it
        if (!newCategory.parent) {
          setFormData(prev => ({ ...prev, category: String(newCategory.id) }));
        } else {
          // If it's a subcategory, select its parent and the subcategory
          setFormData(prev => ({ 
            ...prev, 
            category: String(newCategory.parent),
            subcategory: String(newCategory.id)
          }));
        }
      } catch (error) {
        console.error('Error reloading categories:', error);
      }
    };
    loadAllCategories();
  };

  const handleSubcategoryCreated = (newSubcategory) => {
    // Reload all categories first
    const loadAllCategories = async () => {
      try {
        const response = await categoriesAPI.list({ is_active: 'true' });
        const categoriesData = response.data.results || response.data || [];
        const updatedCategories = Array.isArray(categoriesData) ? categoriesData : [];
        setAllCategories(updatedCategories);
        
        // Reload subcategories for the current category
        const subcatResponse = await categoriesAPI.list({ parent: formData.category, is_active: 'true' });
        const newSubcategories = subcatResponse.data.results || subcatResponse.data || [];
        setSubcategories(newSubcategories);
        
        // Select the newly created subcategory
        setFormData(prev => ({ ...prev, subcategory: String(newSubcategory.id) }));
      } catch (error) {
        console.error('Error reloading categories/subcategories:', error);
      }
    };
    loadAllCategories();
  };

  const handleSupplierCreated = (newSupplier) => {
    // Reload suppliers
    const loadSuppliers = async () => {
      try {
        const response = await suppliersAPI.list({ is_active: 'true' });
        const suppliersData = response.data.results || response.data || [];
        const updatedSuppliers = Array.isArray(suppliersData) ? suppliersData : [];
        setSuppliers(updatedSuppliers);
        
        // Select the newly created supplier
        setFormData(prev => ({ 
          ...prev, 
          supplier: String(newSupplier.id),
          supplier_name: newSupplier.name
        }));
      } catch (error) {
        console.error('Error reloading suppliers:', error);
      }
    };
    loadSuppliers();
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
    
    if (showPricingFields) {
      if (!formData.selling_price || parseFloat(formData.selling_price) < 0) {
        newErrors.selling_price = 'Selling price is required';
      }

      if (showMrp && formData.mrp && parseFloat(formData.mrp) < 0) {
        newErrors.mrp = 'MRP must be zero or positive';
      }

      if (
        showMrp &&
        formData.mrp &&
        formData.selling_price &&
        parseFloat(formData.mrp) < parseFloat(formData.selling_price)
      ) {
        newErrors.mrp = 'MRP should be at least the selling price';
      }

      if (
        showCostField &&
        parseFloat(formData.selling_price) < parseFloat(formData.cost || 0)
      ) {
        newErrors.selling_price = 'Selling price should be greater than or equal to cost';
      }
    }

    if (showCostField && formData.cost && parseFloat(formData.cost) < 0) {
      newErrors.cost = 'Cost must be positive';
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
      const payload = { ...formData };
      if (!fieldAccess.pricing) {
        delete payload.selling_price;
        delete payload.mrp;
        delete payload.tax_rate;
        delete payload.is_taxable;
        if (!product) {
          payload.selling_price = 0;
          payload.mrp = 0;
        }
      }
      if (!fieldAccess.cost) {
        delete payload.cost;
        if (!product) {
          payload.cost = 0;
        }
      }
      if (!fieldAccess.stock) {
        delete payload.stock_quantity;
        delete payload.low_stock_threshold;
        delete payload.reorder_quantity;
        delete payload.track_stock;
        if (!product) {
          payload.stock_quantity = 0;
        }
      }
      if (!variantsEnabled) {
        payload.has_variants = false;
        payload.available_sizes = [];
        payload.available_colors = [];
      }

      const submitData = new FormData();
      
      Object.keys(payload).forEach(key => {
        // Skip SKU and Barcode - they are system-generated
        if (key === 'sku' || key === 'barcode') {
          return;
        }
        if (key === 'available_sizes' || key === 'available_colors') {
          // Handle array fields
          payload[key].forEach(id => {
            submitData.append(key, id);
          });
        } else if (payload[key] !== '' && payload[key] !== null && payload[key] !== undefined) {
          submitData.append(key, payload[key]);
        }
      });
      
      if (image) {
        submitData.append('image', image);
      }

      const needsReason = makerCheckerOn && productEditNeedsReason(payload, product, {
        financialFieldsLocked: makerCheckerFinancialLocked,
      });
      if (needsReason) {
        if (!changeReason.trim()) {
          toast.warning('Enter a reason for this sensitive change.');
          setLoading(false);
          return;
        }
        submitData.append('reason', changeReason.trim());
      }

      let response;
      if (product) {
        response = await productsAPI.update(product.id, submitData);
        if (isPendingApprovalResponse(response.status)) {
          toast.warning(PENDING_APPROVAL_MESSAGE);
        } else {
          toast.success('Product updated successfully');
        }
      } else {
        response = await productsAPI.create(submitData);
        toast.success('Product created successfully');
      }

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

          </div>

          <div className="form-row form-row-paired">
            <div className="form-group">
              <label>Category</label>
              <div className="select-with-add">
                <SearchableSelect
                  name="category"
                  value={formData.category}
                  onChange={handleChange}
                  options={allCategories.filter(cat => !cat.parent).map(cat => ({
                    id: cat.id,
                    name: cat.name,
                  }))}
                  placeholder="Select category…"
                  searchable={true}
                  onAddNew={() => setShowCategoryForm(true)}
                  addNewLabel="+ Add category"
                />
              </div>
            </div>

            <div className="form-group">
              <label>Subcategory</label>
              <div className="select-with-add">
                <SearchableSelect
                  key={`subcategory-${formData.category || 'none'}`}
                  name="subcategory"
                  value={formData.subcategory}
                  onChange={handleChange}
                  options={subcategories.map((subcat) => ({
                    id: subcat.id,
                    name: subcat.name,
                  }))}
                  placeholder={
                    !formData.category
                      ? 'Select category first'
                      : subcategories.length === 0
                        ? 'No subcategories — add one'
                        : 'Select subcategory (optional)'
                  }
                  searchable={true}
                  disabled={!formData.category}
                  onAddNew={
                    formData.category
                      ? () => setShowSubcategoryForm(true)
                      : () => {
                          toast.error('Select a category before adding a subcategory');
                        }
                  }
                  addNewLabel="+ Add subcategory"
                />
                {formData.category && subcategories.length === 0 && (
                  <small className="form-text text-muted">
                    Optional. Use + Add subcategory or leave empty.
                  </small>
                )}
              </div>
            </div>
          </div>

          {variantsEnabled ? (
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
          ) : (
            <p className="mb-2 text-sm text-muted-foreground">
              Size/color variants are turned off. Enable{' '}
              <strong>Products → Product Variants</strong> in Module Settings if you need them.
            </p>
          )}

          {variantsEnabled && formData.has_variants && (
            <>
            {(sizes.length === 0 || colors.length === 0) && (
              <div className="form-banner-error mb-3" role="status">
                {sizes.length === 0 && colors.length === 0
                  ? 'No sizes or colors exist yet. '
                  : sizes.length === 0
                    ? 'No sizes defined yet. '
                    : 'No colors defined yet. '}
                Add them under{' '}
                <Link to="/product-attributes" className="font-medium underline">
                  Sizes &amp; colors
                </Link>
                {' '}(or Sales → Sizes &amp; colors), then return here and select from the lists below.
              </div>
            )}
            <div className="form-row">
              <div className="form-group">
                <label>Available Sizes</label>
                <input
                  type="text"
                  placeholder="Search sizes..."
                  value={sizeSearch}
                  onChange={(e) => setSizeSearch(e.target.value)}
                  style={{ marginBottom: '0.5rem', padding: '0.5rem', width: '100%', border: '1px solid #e5e7eb', borderRadius: '4px' }}
                />
                <select
                  name="available_sizes"
                  multiple
                  value={Array.isArray(formData.available_sizes) ? formData.available_sizes.map(id => String(id)) : []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                    setFormData(prev => ({ ...prev, available_sizes: selected }));
                  }}
                  style={{ minHeight: '100px', width: '100%' }}
                >
                  {sizes
                    .filter(size => 
                      !sizeSearch || 
                      size.name.toLowerCase().includes(sizeSearch.toLowerCase()) ||
                      size.code.toLowerCase().includes(sizeSearch.toLowerCase())
                    )
                    .map(size => (
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
                <input
                  type="text"
                  placeholder="Search colors..."
                  value={colorSearch}
                  onChange={(e) => setColorSearch(e.target.value)}
                  style={{ marginBottom: '0.5rem', padding: '0.5rem', width: '100%', border: '1px solid #e5e7eb', borderRadius: '4px' }}
                />
                <select
                  name="available_colors"
                  multiple
                  value={Array.isArray(formData.available_colors) ? formData.available_colors.map(id => String(id)) : []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                    setFormData(prev => ({ ...prev, available_colors: selected }));
                  }}
                  style={{ minHeight: '100px', width: '100%' }}
                >
                  {colors
                    .filter(color => 
                      !colorSearch || 
                      color.name.toLowerCase().includes(colorSearch.toLowerCase()) ||
                      (color.hex_code && color.hex_code.toLowerCase().includes(colorSearch.toLowerCase()))
                    )
                    .map(color => (
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
            {product?.id && formData.has_variants ? (
              <div className="mt-3">
                <ProductVariantsPanel productId={product.id} />
              </div>
            ) : null}
            </>
          )}

          {showPricingFields && (
          <div className="form-row">
            {showMrp && (
            <div className="form-group">
              <label>MRP (KES)</label>
              <input
                type="number"
                name="mrp"
                value={formData.mrp}
                onChange={handleChange}
                step="0.01"
                min="0"
                placeholder="List / sticker price"
              />
              {errors.mrp && <span className="error">{errors.mrp}</span>}
              <small className="text-muted">Maximum retail price for display</small>
            </div>
            )}

            <div className="form-group">
              <label className={SELLING_PRICE_CLASS}>Selling price (KES) *</label>
              <input
                type="number"
                name="selling_price"
                value={formData.selling_price}
                onChange={handleChange}
                step="0.01"
                min="0"
                required
                className={SELLING_PRICE_CLASS}
              />
              {errors.selling_price && <span className="error">{errors.selling_price}</span>}
              <small className="text-muted">Used at POS, on invoices, and in all reports</small>
            </div>
          </div>
          )}

          {showCostField && (
          <div className="form-row">
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
          )}

          {showStockFields && (
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
          </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Unit</label>
              <SearchableSelect
                name="unit"
                value={formData.unit}
                onChange={handleChange}
                options={unitOptions}
                placeholder="Select unit..."
                searchable={true}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Supplier (Optional)</label>
              <div className="select-with-add">
                <SearchableSelect
                  name="supplier"
                  value={formData.supplier}
                  onChange={handleChange}
                  options={suppliers.map(sup => ({
                    id: sup.id,
                    name: sup.name
                  }))}
                  placeholder="Select supplier (optional)..."
                  searchable={true}
                  onAddNew={() => {
                    setShowSupplierForm(true);
                  }}
                  addNewLabel="+ Add New Supplier"
                />
              </div>
              {formData.supplier_name && !formData.supplier && (
                <small className="form-text">Legacy supplier: {formData.supplier_name}</small>
              )}
              {suppliers.length === 0 && (
                <small className="form-text">No suppliers available. Click "+ Add New Supplier" to create one.</small>
              )}
            </div>

            <div className="form-group">
              <label>Supplier Contact (Legacy - Optional)</label>
              <input
                type="text"
                name="supplier_contact"
                value={formData.supplier_contact}
                onChange={handleChange}
                placeholder="Legacy field - use supplier dropdown above"
                disabled={!!formData.supplier}
              />
              {formData.supplier && (
                <small className="form-text">Using selected supplier above</small>
              )}
            </div>
          </div>

          {showPricingFields && (
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
          </div>
          )}

          {imagesEnabled && (
          <div className="form-row">
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
          )}

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
            {showStockFields && (
            <label>
              <input
                type="checkbox"
                name="track_stock"
                checked={formData.track_stock}
                onChange={handleChange}
              />
              Track Stock
            </label>
            )}
            {showPricingFields && (
            <label>
              <input
                type="checkbox"
                name="is_taxable"
                checked={formData.is_taxable}
                onChange={handleChange}
              />
              Taxable
            </label>
            )}
            {showProductStatus && (
            <label>
              <input
                type="checkbox"
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
              />
              Active
            </label>
            )}
          </div>

          </form>
        </div>
        {makerCheckerOn &&
        productEditNeedsReason(formData, product, {
          financialFieldsLocked: makerCheckerFinancialLocked,
        }) ? (
          <div className="border-t px-4 py-3">
            <ChangeReasonField
              context="catalog"
              value={changeReason}
              onChange={setChangeReason}
            />
          </div>
        ) : null}

        <div className="slide-in-panel-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button type="submit" onClick={handleSubmit} disabled={loading} className="btn btn-primary">
            {loading ? 'Saving...' : product ? 'Update' : 'Create'}
          </button>
        </div>
      </div>

      {/* Category Form - Nested Slide-in Panel */}
      <CategoryForm
        isOpen={showCategoryForm}
        onClose={() => setShowCategoryForm(false)}
        onSave={handleCategoryCreated}
        categories={allCategories}
      />

      {/* Subcategory Form - Nested Slide-in Panel */}
      <CategoryForm
        isOpen={showSubcategoryForm}
        onClose={() => setShowSubcategoryForm(false)}
        onSave={handleSubcategoryCreated}
        parentCategory={formData.category}
        categories={allCategories}
      />

      {/* Supplier Form - Nested Slide-in Panel - Only show when explicitly requested */}
      {showSupplierForm && (
        <SupplierForm
          supplier={null}
          onClose={() => setShowSupplierForm(false)}
          onSave={handleSupplierCreated}
        />
      )}
    </div>
  );
};

export default ProductForm;

