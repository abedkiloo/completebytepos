import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
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
  STOCK_OPENING_LABEL,
  STOCK_OPENING_HINT,
} from '../../utils/productDisplay';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { useProductUnits } from '../../hooks/useProductUnits';
import ChangeReasonField from '../Approvals/ChangeReasonField';
import ProductVariantsPanel from './ProductVariantsPanel';
import VariantDraftSummary from './VariantDraftSummary';
import {
  combinationsPayloadFromKeys,
  unionSizeColorIdsFromKeys,
  buildRowFromKey,
  combinationRowLabel,
} from '../../utils/variantCombinations';
import {
  variantDraftNumericValidationMessage,
  variantFinancialValidationMessage,
} from '../../utils/variantPayload';
import {
  extractApiReasonError,
  extractPendingChange,
  isMakerCheckerEnabled,
  isPendingApprovalResponse,
  pendingApprovalToastMessage,
  productEditNeedsReason,
  proposedPendingCost,
} from '../../utils/makerChecker';
import { formatCurrency } from '../../utils/formatters';
import PendingApprovalBadges from '../Approvals/PendingApprovalBadges';
import {
  crossParentSubcategoryHint,
  fetchSubcategories,
  findCategoryByExactName,
  mergeCategoryOptions,
  resolveSubcategoryDuplicate,
} from '../../utils/categorySelect';
import { applyVariantDraftsAfterProductSave } from '../../utils/variantDrafts';

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
  const [pendingApproval, setPendingApproval] = useState(null);
  const variantDraftsRef = useRef({});
  const [variantDrafts, setVariantDrafts] = useState({});
  const [variantCombinationKeys, setVariantCombinationKeys] = useState([]);
  const handleVariantDraftsChange = useCallback((drafts) => {
    const next = drafts || {};
    variantDraftsRef.current = next;
    setVariantDrafts(next);
  }, []);
  const handleVariantCombinationKeysChange = useCallback((keys) => {
    const list = Array.isArray(keys) ? keys : [];
    setVariantCombinationKeys(list);
    const { sizeIds, colorIds } = unionSizeColorIdsFromKeys(list);
    setFormData((prev) => ({
      ...prev,
      available_sizes: sizeIds,
      available_colors: colorIds,
    }));
  }, []);
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
  const [subcategorySearchTerm, setSubcategorySearchTerm] = useState('');
  const debouncedSubcategorySearch = useDebouncedValue(subcategorySearchTerm);
  const [subcategoryHint, setSubcategoryHint] = useState('');
  const [subcategoryFormInitialName, setSubcategoryFormInitialName] = useState('');
  const [sizes, setSizes] = useState([]);
  const [colors, setColors] = useState([]);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [showSubcategoryForm, setShowSubcategoryForm] = useState(false);
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [allCategories, setAllCategories] = useState([]);
  const [suppliers, setSuppliers] = useState([]);

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
    if (!formData.category) {
      setSubcategories([]);
      setSubcategorySearchTerm('');
      setSubcategoryHint('');
      if (formData.subcategory) {
        setFormData((prev) => ({ ...prev, subcategory: '' }));
      }
      return undefined;
    }

    const categoryId = parseInt(formData.category, 10);
    if (Number.isNaN(categoryId)) {
      setSubcategories([]);
      return undefined;
    }

    let cancelled = false;
    (async () => {
      try {
        const rows = await fetchSubcategories(categoryId);
        if (cancelled) return;
        setSubcategories(rows);

        if (formData.subcategory) {
          const subcategoryId = parseInt(formData.subcategory, 10);
          const subcategoryExists = rows.some((sub) => sub.id === subcategoryId);
          if (!subcategoryExists) {
            setFormData((prev) => ({ ...prev, subcategory: '' }));
          }
        }
      } catch (error) {
        console.error('Error loading subcategories:', error);
        if (!cancelled) {
          setSubcategories([]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [formData.category]);

  useEffect(() => {
    const term = debouncedSubcategorySearch.trim();
    if (!term || !formData.category) {
      setSubcategoryHint('');
      return undefined;
    }

    const localMatch = subcategories.some((sub) =>
      sub.name?.toLowerCase().includes(term.toLowerCase())
    );
    if (localMatch) {
      setSubcategoryHint('');
      return undefined;
    }

    let cancelled = false;
    (async () => {
      try {
        const exact = await findCategoryByExactName(term);
        if (cancelled) return;
        const parent = allCategories.find(
          (c) => String(c.id) === String(formData.category)
        );
        setSubcategoryHint(
          crossParentSubcategoryHint(exact, formData.category, parent?.name)
        );
      } catch {
        if (!cancelled) setSubcategoryHint('');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [debouncedSubcategorySearch, formData.category, subcategories, allCategories]);

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
        cost: product.cost ?? '',
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
      setPendingApproval(product.pending_approval || null);
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
    const loadAllCategories = async () => {
      try {
        const response = await categoriesAPI.list({ is_active: 'true' });
        const categoriesData = response.data.results || response.data || [];
        const updatedCategories = Array.isArray(categoriesData) ? categoriesData : [];
        setAllCategories(updatedCategories);

        const rows = await fetchSubcategories(formData.category);
        setSubcategories(rows);
        setSubcategorySearchTerm('');
        setSubcategoryHint('');
        setSubcategoryFormInitialName('');
        setFormData((prev) => ({ ...prev, subcategory: String(newSubcategory.id) }));
      } catch (error) {
        console.error('Error reloading categories/subcategories:', error);
      }
    };
    loadAllCategories();
  };

  const handleResolveSubcategoryDuplicate = async (name) => {
    const result = await resolveSubcategoryDuplicate(name, formData.category);
    if (!result) return false;

    if (result.sameParent) {
      const rows = await fetchSubcategories(formData.category);
      setSubcategories((prev) => mergeCategoryOptions(prev, rows));
      setFormData((prev) => ({ ...prev, subcategory: String(result.existing.id) }));
      setShowSubcategoryForm(false);
      setSubcategoryFormInitialName('');
      toast.info(
        `"${result.existing.name}" is already under this category — selected it for you.`
      );
      return true;
    }

    const otherParent = allCategories.find(
      (c) => String(c.id) === String(result.existing.parent)
    );
    toast.error(
      crossParentSubcategoryHint(
        result.existing,
        formData.category,
        otherParent?.name
      )
    );
    return false;
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
    
    if (showPricingFields && !formData.has_variants) {
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
        const selling = parseFloat(formData.selling_price) || 0;
        const cost = parseFloat(formData.cost) || 0;
        newErrors.cost = `Cost (${cost}) cannot be higher than selling price (${selling}). Increase selling price or lower cost.`;
      }
    }

    if (showCostField && !formData.has_variants && formData.cost && parseFloat(formData.cost) < 0) {
      newErrors.cost = 'Cost must be positive';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const sensitiveProductEdit = useMemo(
    () =>
      makerCheckerOn &&
      product &&
      productEditNeedsReason(formData, product, {
        financialFieldsLocked: makerCheckerFinancialLocked,
        variantProduct: formData.has_variants,
        fieldAccess,
      }),
    [makerCheckerOn, product, formData, makerCheckerFinancialLocked, fieldAccess]
  );

  const pendingCost = proposedPendingCost(pendingApproval);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validate()) {
      return;
    }

    if (variantsEnabled && formData.has_variants && variantCombinationKeys.length === 0) {
      toast.warning('Add at least one variant combination (size and/or color) before saving.');
      return;
    }

    if (variantsEnabled && formData.has_variants) {
      for (const key of variantCombinationKeys) {
        const draft = variantDraftsRef.current[key];
        if (!draft) continue;
        const row = buildRowFromKey(key, [], sizes, colors);
        const label = combinationRowLabel(row);
        const numericError = variantDraftNumericValidationMessage(draft, {
          label,
          canEditMrp: showMrp && showPricingFields,
          canEditCost: showCostField,
          allowStockInput: showStockFields && !product,
        });
        if (numericError) {
          toast.warning(numericError);
          return;
        }
        const financialError = variantFinancialValidationMessage(draft, {
          label,
          canEditMrp: showMrp && showPricingFields,
        });
        if (financialError) {
          toast.warning(financialError);
          return;
        }
      }
    }

    setLoading(true);
    try {
      const payload = { ...formData };
      if (payload.has_variants) {
        delete payload.selling_price;
        delete payload.mrp;
        delete payload.cost;
        delete payload.stock_quantity;
        delete payload.low_stock_threshold;
        delete payload.reorder_quantity;
      }
      if (product) {
        delete payload.stock_quantity;
        delete payload.low_stock_threshold;
        delete payload.reorder_quantity;
        delete payload.track_stock;
      }
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

      if (payload.has_variants && variantCombinationKeys.length) {
        submitData.append(
          'variant_combinations',
          JSON.stringify(combinationsPayloadFromKeys(variantCombinationKeys))
        );
      }

      const needsReason =
        makerCheckerOn &&
        product &&
        productEditNeedsReason(payload, product, {
          financialFieldsLocked: makerCheckerFinancialLocked,
          variantProduct: payload.has_variants,
          fieldAccess,
        });
      if (needsReason) {
        if (!changeReason.trim()) {
          toast.warning(
            'Enter a reason below — price, cost, or stock changes need manager approval.'
          );
          setLoading(false);
          return;
        }
        submitData.append('reason', changeReason.trim());
      }

      let response;
      let savedProductId = product?.id;
      if (product) {
        response = await productsAPI.update(product.id, submitData);
        if (isPendingApprovalResponse(response.status)) {
          toast.warning(pendingApprovalToastMessage());
          const refreshed = response.data?.product;
          if (refreshed?.pending_approval) {
            setPendingApproval(refreshed.pending_approval);
          } else if (extractPendingChange(response.data)) {
            setPendingApproval((prev) => ({
              ...(prev || {}),
              pending_price: true,
              message: 'Pending approval — changes not yet active',
            }));
          }
        } else {
          toast.success('Product updated successfully');
          setPendingApproval(response.data?.pending_approval || null);
        }
      } else {
        response = await productsAPI.create(submitData);
        savedProductId = response.data?.id;
        toast.success('Product created successfully');
      }

      if (payload.has_variants && savedProductId && Object.keys(variantDraftsRef.current).length) {
        try {
          const { applied } = await applyVariantDraftsAfterProductSave(
            savedProductId,
            variantDraftsRef.current,
            { includeStock: !product && showStockFields && fieldAccess.stock }
          );
          if (applied > 0) {
            toast.success(
              product
                ? `Updated ${applied} variant row(s)`
                : `Updated price and stock for ${applied} variant row(s)`
            );
          }
        } catch (err) {
          const detail = err?.message || 'Edit variants and try again.';
          toast.warning(
            product
              ? `Product saved, but some variant price or cost values could not be applied. ${detail}`
              : `Product saved, but some variant price or stock values could not be applied. ${detail}`
          );
        }
      }

      setTimeout(() => {
        onSave();
      }, 200);
    } catch (error) {
      if (error.response?.data) {
        const raw = error.response.data;
        const mapped = {};
        Object.entries(raw).forEach(([key, val]) => {
          const msg = Array.isArray(val) ? val.join(' ') : String(val);
          if (key === 'price') {
            mapped.selling_price = msg;
          } else {
            mapped[key] = msg;
          }
        });
        setErrors(mapped);
        const errorMessage =
          extractApiReasonError(raw) ||
          raw.error ||
          mapped.cost ||
          mapped.selling_price ||
          mapped.price ||
          Object.values(mapped).join(', ') ||
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
                  onSearchTermChange={setSubcategorySearchTerm}
                  noResultsHint={subcategoryHint}
                  onAddNew={
                    formData.category
                      ? () => {
                          setSubcategoryFormInitialName(subcategorySearchTerm.trim());
                          setShowSubcategoryForm(true);
                        }
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
            <div className="mt-2">
              <p className="mb-2 text-sm text-muted-foreground">
                Build variants one at a time — pick a size and color, click{' '}
                <strong>Add variant</strong>, then enter
                {showMrp && showPricingFields ? ' MRP,' : ''} price
                {showCostField ? ', cost' : ''}
                {showStockFields && !product ? ', and opening stock' : ''}{' '}
                for that row.
              </p>
              <ProductVariantsPanel
                productId={product?.id}
                sizes={sizes}
                colors={colors}
                canEditPrice={showPricingFields}
                canEditMrp={showMrp && showPricingFields}
                canEditStock={showStockFields && !product}
                canEditCost={showCostField}
                onDraftsChange={handleVariantDraftsChange}
                onCombinationKeysChange={handleVariantCombinationKeysChange}
              />
            </div>
            </>
          )}

          {showPricingFields && !formData.has_variants && (
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

          {showCostField && !formData.has_variants && (
          <div className="form-row">
            <div className="form-group">
              <label className="inline-flex flex-wrap items-center gap-2">
                Cost (KES)
                <PendingApprovalBadges pendingApproval={pendingApproval} />
              </label>
              <input
                type="number"
                name="cost"
                value={formData.cost}
                onChange={handleChange}
                step="0.01"
                min="0"
              />
              {errors.cost && <span className="error">{errors.cost}</span>}
              {pendingCost != null && (
                <small className="mt-1 block text-amber-700">
                  Pending approval: {formatCurrency(pendingCost)} (current live cost:{' '}
                  {formatCurrency(product?.cost ?? 0)})
                </small>
              )}
            </div>
          </div>
          )}

          {showStockFields && !formData.has_variants && !product && (
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="product-opening-stock">{STOCK_OPENING_LABEL}</label>
              <small className="form-text">{STOCK_OPENING_HINT}</small>
              <input
                id="product-opening-stock"
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
            {showStockFields && !product && (
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
        {sensitiveProductEdit ? (
          <div className="border-t border-amber-200/80 bg-amber-50/30 px-4 py-3 dark:border-amber-900 dark:bg-amber-950/20">
            <ChangeReasonField
              context="catalog"
              value={changeReason}
              onChange={setChangeReason}
            />
          </div>
        ) : null}

        {variantsEnabled && formData.has_variants ? (
          <div className="border-t border-border px-4 py-3">
            <VariantDraftSummary
              productName={formData.name}
              draftsByKey={variantDrafts}
              sizes={sizes}
              colors={colors}
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
        onClose={() => {
          setShowSubcategoryForm(false);
          setSubcategoryFormInitialName('');
        }}
        onSave={handleSubcategoryCreated}
        onResolveDuplicate={handleResolveSubcategoryDuplicate}
        initialName={subcategoryFormInitialName}
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

