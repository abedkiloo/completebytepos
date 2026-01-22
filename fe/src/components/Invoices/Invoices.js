import React, { useState, useEffect } from 'react';
import { invoicesAPI, paymentsAPI, customersAPI, salesAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import '../../styles/shared.css';
import '../../styles/slide-in-panel.css';
import './Invoices.css';

const Invoices = () => {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [sales, setSales] = useState([]);
  const [products, setProducts] = useState([]);
  const [formData, setFormData] = useState({
    customer_id: '',
    customer_name: '',
    customer_email: '',
    customer_phone: '',
    customer_address: '',
    subtotal: 0,
    tax_amount: 0,
    discount_amount: 0,
    total: 0,
    due_date: '',
    notes: '',
    status: 'draft',
    items: [],
  });
  const [paymentData, setPaymentData] = useState({
    amount: '',
    payment_method: 'cash',
    payment_date: new Date().toISOString().split('T')[0],
    reference: '',
    notes: '',
  });

  useEffect(() => {
    loadInvoices();
    loadCustomers();
    loadSales();
    loadProducts();
  }, [searchQuery, statusFilter]);

  // Reload customers when modal opens to ensure we have the latest customers
  useEffect(() => {
    if (showModal) {
      loadCustomers();
    }
  }, [showModal]);

  // Refresh customers when window regains focus (in case user added a customer in another tab)
  useEffect(() => {
    if (!showModal) return;

    const handleFocus = () => {
      loadCustomers();
    };

    // Also refresh on visibility change (when tab becomes visible)
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadCustomers();
      }
    };

    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [showModal]);

  const loadInvoices = async () => {
    setLoading(true);
    try {
      const params = {};
      if (searchQuery) {
        params.search = searchQuery;
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const response = await invoicesAPI.list(params);
      const invoicesData = response.data.results || response.data || [];
      setInvoices(Array.isArray(invoicesData) ? invoicesData : []);
    } catch (error) {
      console.error('Error loading invoices:', error);
      toast.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  };

  const loadCustomers = async () => {
    try {
      // Load all active customers - request a large page size to get all customers
      // The API is paginated with PAGE_SIZE: 20, so we need to request more
      const response = await customersAPI.list({ is_active: 'true', page_size: 1000 });
      const customersData = response.data.results || response.data || [];
      setCustomers(Array.isArray(customersData) ? customersData : []);
    } catch (error) {
      console.error('Error loading customers:', error);
      toast.error('Failed to load customers');
    }
  };

  const loadSales = async () => {
    try {
      const response = await salesAPI.list({ limit: 100 });
      setSales(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading sales:', error);
    }
  };

  const loadProducts = async () => {
    try {
      const response = await productsAPI.list({ is_active: 'true', page_size: 1000 });
      const productsData = response.data.results || response.data || [];
      setProducts(Array.isArray(productsData) ? productsData : []);
    } catch (error) {
      console.error('Error loading products:', error);
    }
  };

  const handleCreate = async () => {
    setSelectedInvoice(null);
    setFormData({
      customer_id: '',
      customer_name: '',
      customer_email: '',
      customer_phone: '',
      customer_address: '',
      subtotal: 0,
      tax_amount: 0,
      discount_amount: 0,
      total: 0,
      due_date: '',
      notes: '',
      status: 'draft',
      items: [],
    });
    // Reload customers to include any newly created ones
    await loadCustomers();
    setShowModal(true);
  };

  const handleEdit = async (invoice) => {
    try {
      // Fetch full invoice details including items
      const fullInvoice = await invoicesAPI.get(invoice.id);
      const invoiceData = fullInvoice.data;
      
      setSelectedInvoice(invoiceData);
      
      // Format due_date to YYYY-MM-DD format if it exists
      let formattedDueDate = '';
      if (invoiceData.due_date) {
        const date = new Date(invoiceData.due_date);
        if (!isNaN(date.getTime())) {
          formattedDueDate = date.toISOString().split('T')[0];
        }
      }
      
      // Format items for editing - convert backend format to form format
      const formattedItems = (invoiceData.items || []).map(item => ({
        product_id: item.product || item.product_id,
        product: item.product || item.product_id,
        quantity: item.quantity || 1,
        unit_price: parseFloat(item.unit_price) || 0,
        subtotal: parseFloat(item.subtotal) || 0,
        description: item.description || '',
      }));
      
      setFormData({
        customer_id: invoiceData.customer || '',
        customer_name: invoiceData.customer_name || '',
        customer_email: invoiceData.customer_email || '',
        customer_phone: invoiceData.customer_phone || '',
        customer_address: invoiceData.customer_address || '',
        subtotal: invoiceData.subtotal || 0,
        tax_amount: invoiceData.tax_amount || 0,
        discount_amount: invoiceData.discount_amount || 0,
        total: invoiceData.total || 0,
        due_date: formattedDueDate,
        notes: invoiceData.notes || '',
        status: invoiceData.status || 'draft',
        items: formattedItems,
      });
      // Reload customers to include any newly created ones
      await loadCustomers();
      setShowModal(true);
    } catch (error) {
      console.error('Error loading invoice details:', error);
      toast.error('Failed to load invoice details');
    }
  };

  const handleAddPayment = (invoice) => {
    setSelectedInvoice(invoice);
    setPaymentData({
      amount: invoice.balance > 0 ? invoice.balance.toString() : '',
      payment_method: 'cash',
      payment_date: new Date().toISOString().split('T')[0],
      reference: '',
      notes: '',
    });
    setShowPaymentModal(true);
  };

  const handleDelete = (invoice) => {
    setSelectedInvoice(invoice);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedInvoice) return;
    
    try {
      await invoicesAPI.delete(selectedInvoice.id);
      toast.success('Invoice deleted successfully');
      loadInvoices();
      setShowDeleteConfirm(false);
      setSelectedInvoice(null);
    } catch (error) {
      toast.error('Failed to delete invoice: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      // Format items for API - only include items with product_id
      const formattedItems = (formData.items || [])
        .filter(item => item.product_id)
        .map(item => ({
          product: item.product_id || item.product,
          quantity: parseInt(item.quantity) || 1,
          unit_price: parseFloat(item.unit_price) || 0,
          description: item.description || '',
        }));
      
      const invoiceData = {
        ...formData,
        subtotal: parseFloat(formData.subtotal) || 0,
        tax_amount: parseFloat(formData.tax_amount) || 0,
        discount_amount: parseFloat(formData.discount_amount) || 0,
        total: parseFloat(formData.total) || 0,
        customer_id: formData.customer_id || null,
        due_date: formData.due_date || null,
        // Items should be provided when creating manually, or sale_id when creating from sale
        items: formattedItems,
        sale_id: formData.sale_id || null,
      };
      
      // Validate that invoice has items when creating manually (not from sale)
      if (!selectedInvoice && !invoiceData.sale_id) {
        if (!formattedItems || formattedItems.length === 0) {
          toast.error('An invoice must have at least one item. Please add items to the invoice or create from a sale.');
          return;
        }
      }
      
      if (selectedInvoice) {
        await invoicesAPI.update(selectedInvoice.id, invoiceData);
        toast.success('Invoice updated successfully');
      } else {
        await invoicesAPI.create(invoiceData);
        toast.success('Invoice created successfully');
      }
      setShowModal(false);
      loadInvoices();
      setSelectedInvoice(null);
    } catch (error) {
      toast.error('Failed to save invoice: ' + (error.response?.data?.error || error.message));
    }
  };

  // Calculate subtotal from items
  const calculateSubtotalFromItems = (items) => {
    return items.reduce((sum, item) => {
      const quantity = parseFloat(item.quantity) || 0;
      const unitPrice = parseFloat(item.unit_price) || 0;
      return sum + (quantity * unitPrice);
    }, 0);
  };

  // Update total when items, tax, or discount change
  useEffect(() => {
    const itemsSubtotal = calculateSubtotalFromItems(formData.items || []);
    const tax = parseFloat(formData.tax_amount) || 0;
    const discount = parseFloat(formData.discount_amount) || 0;
    const total = itemsSubtotal + tax - discount;
    
    setFormData(prev => {
      // Only update if values have actually changed
      if (Math.abs(prev.subtotal - itemsSubtotal) < 0.01 && Math.abs(prev.total - total) < 0.01) {
        return prev; // No change needed
      }
      return {
        ...prev,
        subtotal: itemsSubtotal,
        total: Math.max(0, total),
      };
    });
  }, [formData.items, formData.tax_amount, formData.discount_amount]); // eslint-disable-line react-hooks/exhaustive-deps

  // Add item to invoice
  const handleAddItem = () => {
    setFormData(prev => ({
      ...prev,
      items: [...(prev.items || []), {
        product: null,
        product_id: '',
        quantity: 1,
        unit_price: 0,
        subtotal: 0,
        description: '',
      }],
    }));
  };

  // Remove item from invoice
  const handleRemoveItem = (index) => {
    setFormData(prev => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== index),
    }));
  };

  // Update item field
  const handleItemChange = (index, field, value) => {
    setFormData(prev => {
      const newItems = [...prev.items];
      newItems[index] = {
        ...newItems[index],
        [field]: value,
      };
      
      // Auto-calculate subtotal for this item
      if (field === 'quantity' || field === 'unit_price') {
        const quantity = parseFloat(newItems[index].quantity) || 0;
        const unitPrice = parseFloat(newItems[index].unit_price) || 0;
        newItems[index].subtotal = quantity * unitPrice;
      }
      
      return {
        ...prev,
        items: newItems,
      };
    });
  };

  // Handle product selection for item
  const handleItemProductChange = (index, productId) => {
    const product = products.find(p => p.id === parseInt(productId));
    if (product) {
      handleItemChange(index, 'product_id', product.id);
      handleItemChange(index, 'product', product.id);
      handleItemChange(index, 'unit_price', product.selling_price || product.price || 0);
    }
  };

  const handlePaymentSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedInvoice) return;
    
    try {
      const paymentPayload = {
        invoice: selectedInvoice.id,
        amount: parseFloat(paymentData.amount),
        payment_method: paymentData.payment_method,
        payment_date: paymentData.payment_date,
        reference: paymentData.reference,
        notes: paymentData.notes,
      };
      
      await paymentsAPI.create(paymentPayload);
      toast.success('Payment recorded successfully');
      setShowPaymentModal(false);
      loadInvoices();
      setSelectedInvoice(null);
    } catch (error) {
      toast.error('Failed to record payment: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleCustomerChange = (e) => {
    const customerId = e.target.value;
    const customer = customers.find(c => c.id === parseInt(customerId));
    if (customer) {
      setFormData({
        ...formData,
        customer_id: customer.id,
        customer_name: customer.name,
        customer_email: customer.email || '',
        customer_phone: customer.phone || '',
        customer_address: customer.address || '',
      });
    } else {
      // Clear customer data if no customer selected
      setFormData({
        ...formData,
        customer_id: '',
        customer_name: '',
        customer_email: '',
        customer_phone: '',
        customer_address: '',
      });
    }
  };

  // Transform customers for SearchableSelect component
  const customerOptions = customers.map(customer => ({
    id: customer.id,
    name: `${customer.name}${customer.customer_code ? ` (${customer.customer_code})` : ''}`,
  }));

  const getStatusColor = (status) => {
    const colors = {
      draft: 'gray',
      sent: 'blue',
      partial: 'orange',
      paid: 'green',
      overdue: 'red',
      cancelled: 'gray',
    };
    return colors[status] || 'gray';
  };

  const calculateTotal = () => {
    const subtotal = parseFloat(formData.subtotal) || 0;
    const tax = parseFloat(formData.tax_amount) || 0;
    const discount = parseFloat(formData.discount_amount) || 0;
    return subtotal + tax - discount;
  };

  useEffect(() => {
    const total = calculateTotal();
    setFormData(prev => ({ ...prev, total }));
  }, [formData.subtotal, formData.tax_amount, formData.discount_amount]);

  return (
    <Layout>
      <div className="invoices-container">
        <div className="page-header">
          <div className="page-header-content">
            <h1>Invoices</h1>
            <p>Manage invoices and track payments</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={handleCreate}>
              <span>+</span>
              <span>Create Invoice</span>
            </button>
          </div>
        </div>

        <div className="invoices-toolbar">
          <div className="search-box">
            <input
              type="text"
              placeholder="Search invoices..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <span className="search-icon">🔍</span>
          </div>
          <SearchableSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="status-filter"
            options={[
              { id: 'all', name: 'All Status' },
              { id: 'draft', name: 'Draft' },
              { id: 'sent', name: 'Sent' },
              { id: 'partial', name: 'Partially Paid' },
              { id: 'paid', name: 'Paid' },
              { id: 'overdue', name: 'Overdue' },
              { id: 'cancelled', name: 'Cancelled' }
            ]}
            placeholder="All Status"
          />
        </div>

        {loading ? (
          <div className="loading">Loading invoices...</div>
        ) : (
          <div className="invoices-table-container">
            <table className="invoices-table">
              <thead>
                <tr>
                  <th>Invoice #</th>
                  <th>Customer</th>
                  <th>Date</th>
                  <th>Due Date</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Balance</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan="9" className="empty-state">
                      No invoices found
                    </td>
                  </tr>
                ) : (
                  invoices.map(invoice => (
                    <tr key={invoice.id}>
                      <td>
                        <strong>{invoice.invoice_number}</strong>
                      </td>
                      <td>
                        <div className="customer-name">
                          {invoice.customer_name || invoice.customer_detail?.name || 'N/A'}
                        </div>
                        {invoice.customer_email && (
                          <div className="customer-email">{invoice.customer_email}</div>
                        )}
                      </td>
                      <td>{new Date(invoice.created_at).toLocaleDateString()}</td>
                      <td>
                        {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : '-'}
                      </td>
                      <td>{formatCurrency(invoice.total)}</td>
                      <td>{formatCurrency(invoice.amount_paid || 0)}</td>
                      <td>
                        <span className={invoice.balance > 0 ? 'outstanding' : 'paid'}>
                          {formatCurrency(invoice.balance || 0)}
                        </span>
                      </td>
                      <td>
                        <span className={`status-badge ${getStatusColor(invoice.status)}`}>
                          {invoice.status.charAt(0).toUpperCase() + invoice.status.slice(1)}
                        </span>
                      </td>
                      <td>
                        <div className="action-buttons">
                          <button onClick={() => handleEdit(invoice)} className="btn-edit">View</button>
                          <button 
                            onClick={() => invoicesAPI.downloadPDF(invoice.id)} 
                            className="btn-download"
                            title="Download PDF"
                          >
                            📥 PDF
                          </button>
                          {invoice.balance > 0 && (
                            <button onClick={() => handleAddPayment(invoice)} className="btn-payment">
                              Payment
                            </button>
                          )}
                          <button onClick={() => handleDelete(invoice)} className="btn-delete">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Invoice Modal */}
        {showModal && (
          <div className="slide-in-overlay" onClick={() => setShowModal(false)}>
            <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
              <div className="slide-in-panel-header">
                <h2>{selectedInvoice ? 'Edit Invoice' : 'Create Invoice'}</h2>
                <button onClick={() => setShowModal(false)} className="slide-in-panel-close">×</button>
              </div>
              <div className="slide-in-panel-body">
                <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label>Customer</label>
                  <SearchableSelect
                    value={formData.customer_id || ''}
                    onChange={handleCustomerChange}
                    options={customerOptions}
                    placeholder="Select Customer"
                    name="customer_id"
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Customer Name</label>
                    <input
                      type="text"
                      value={formData.customer_name}
                      onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      value={formData.customer_email}
                      onChange={(e) => setFormData({ ...formData, customer_email: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Phone</label>
                    <input
                      type="text"
                      value={formData.customer_phone}
                      onChange={(e) => setFormData({ ...formData, customer_phone: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Due Date</label>
                    <input
                      type="date"
                      value={formData.due_date}
                      onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Address</label>
                  <textarea
                    value={formData.customer_address}
                    onChange={(e) => setFormData({ ...formData, customer_address: e.target.value })}
                    rows="2"
                  />
                </div>

                {/* Invoice Items Management - Editable when creating/editing */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label>Invoice Items</label>
                    <button
                      type="button"
                      onClick={handleAddItem}
                      className="btn btn-primary"
                      style={{ padding: '0.5rem 1rem', fontSize: '0.875rem' }}
                    >
                      + Add Item
                    </button>
                  </div>
                  
                  {formData.items && formData.items.length > 0 ? (
                    <div className="invoice-items-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Product</th>
                            <th>Qty</th>
                            <th>Unit Price</th>
                            <th>Subtotal</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {formData.items.map((item, idx) => {
                            const productOptions = products.map(p => ({
                              id: p.id,
                              name: `${p.name}${p.sku ? ` (${p.sku})` : ''}`,
                            }));
                            
                            return (
                              <tr key={idx}>
                                <td>
                                  <SearchableSelect
                                    value={item.product_id || ''}
                                    onChange={(e) => handleItemProductChange(idx, e.target.value)}
                                    options={productOptions}
                                    placeholder="Select Product"
                                  />
                                </td>
                                <td>
                                  <input
                                    type="number"
                                    min="1"
                                    step="1"
                                    value={item.quantity || ''}
                                    onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                                    style={{ width: '80px', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px' }}
                                  />
                                </td>
                                <td>
                                  <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={item.unit_price || ''}
                                    onChange={(e) => handleItemChange(idx, 'unit_price', e.target.value)}
                                    style={{ width: '100px', padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px' }}
                                  />
                                </td>
                                <td className="item-subtotal">
                                  {formatCurrency(item.subtotal || 0)}
                                </td>
                                <td>
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveItem(idx)}
                                    className="btn-delete"
                                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                                  >
                                    Remove
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: '1rem', textAlign: 'center', color: '#6b7280', background: '#f9fafb', borderRadius: '8px', border: '1px dashed #d1d5db' }}>
                      No items added. Click "Add Item" to add products to this invoice.
                    </div>
                  )}
                </div>

                {/* Invoice Items Display - Read-only when viewing existing invoice */}
                {selectedInvoice && selectedInvoice.items && selectedInvoice.items.length > 0 && (
                  <div className="form-group">
                    <label>Invoice Items</label>
                    <div className="invoice-items-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Item</th>
                            <th>Qty</th>
                            <th>Unit Price</th>
                            <th>Subtotal</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedInvoice.items.map((item, idx) => {
                            const variantInfo = [];
                            if (item.size_name) variantInfo.push(`Size: ${item.size_name}`);
                            if (item.color_name) variantInfo.push(`Color: ${item.color_name}`);
                            const variantStr = variantInfo.length > 0 ? ` (${variantInfo.join(', ')})` : '';
                            const displayName = `${item.product_name || 'N/A'}${variantStr}`;
                            
                            return (
                              <tr key={item.id || idx}>
                                <td>
                                  <div className="item-name">{displayName}</div>
                                  {item.product_sku && (
                                    <div className="item-sku">SKU: {item.product_sku}</div>
                                  )}
                                  {item.description && (
                                    <div className="item-description">{item.description}</div>
                                  )}
                                </td>
                                <td>{item.quantity}</td>
                                <td>{formatCurrency(item.unit_price)}</td>
                                <td className="item-subtotal">{formatCurrency(item.subtotal)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div className="form-row">
                  <div className="form-group">
                    <label>Subtotal</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.subtotal}
                      onChange={(e) => setFormData({ ...formData, subtotal: e.target.value })}
                      readOnly
                      className="readonly"
                      title="Subtotal is calculated from items"
                    />
                  </div>
                  <div className="form-group">
                    <label>Tax Amount</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.tax_amount}
                      onChange={(e) => setFormData({ ...formData, tax_amount: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Discount Amount</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.discount_amount}
                      onChange={(e) => setFormData({ ...formData, discount_amount: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Total</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.total}
                      readOnly
                      className="readonly"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <SearchableSelect
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    options={[
                      { id: 'draft', name: 'Draft' },
                      { id: 'sent', name: 'Sent' },
                      { id: 'partial', name: 'Partially Paid' },
                      { id: 'paid', name: 'Paid' },
                      { id: 'cancelled', name: 'Cancelled' }
                    ]}
                    placeholder="Select Status"
                  />
                </div>
                <div className="form-group">
                  <label>Notes</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows="3"
                  />
                </div>
                <div className="slide-in-panel-footer">
                  <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary">
                    {selectedInvoice ? 'Update' : 'Create'}
                  </button>
                </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Payment Modal */}
        {showPaymentModal && selectedInvoice && (
          <div className="slide-in-overlay" onClick={() => setShowPaymentModal(false)}>
            <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
              <div className="slide-in-panel-header">
                <h2>Record Payment</h2>
                <button onClick={() => setShowPaymentModal(false)} className="slide-in-panel-close">×</button>
              </div>
              <div className="slide-in-panel-body">
                <div className="payment-info">
                  <p><strong>Invoice:</strong> {selectedInvoice.invoice_number}</p>
                  <p><strong>Total:</strong> {formatCurrency(selectedInvoice.total)}</p>
                  <p><strong>Paid:</strong> {formatCurrency(selectedInvoice.amount_paid || 0)}</p>
                  <p><strong>Balance:</strong> {formatCurrency(selectedInvoice.balance || 0)}</p>
                </div>
                <form onSubmit={handlePaymentSubmit}>
                <div className="form-group">
                  <label>Amount *</label>
                  <input
                    type="number"
                    step="0.01"
                    value={paymentData.amount}
                    onChange={(e) => setPaymentData({ ...paymentData, amount: e.target.value })}
                    max={selectedInvoice.balance}
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Payment Method *</label>
                    <SearchableSelect
                      value={paymentData.payment_method}
                      onChange={(e) => setPaymentData({ ...paymentData, payment_method: e.target.value })}
                      options={[
                        { id: 'cash', name: 'Cash' },
                        { id: 'mpesa', name: 'M-PESA' },
                        { id: 'bank_transfer', name: 'Bank Transfer' },
                        { id: 'cheque', name: 'Cheque' },
                        { id: 'card', name: 'Card' },
                        { id: 'other', name: 'Other' }
                      ]}
                      placeholder="Select Payment Method"
                    />
                  </div>
                  <div className="form-group">
                    <label>Payment Date *</label>
                    <input
                      type="date"
                      value={paymentData.payment_date}
                      onChange={(e) => setPaymentData({ ...paymentData, payment_date: e.target.value })}
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Reference Number</label>
                  <input
                    type="text"
                    value={paymentData.reference}
                    onChange={(e) => setPaymentData({ ...paymentData, reference: e.target.value })}
                    placeholder="Payment reference (e.g., M-PESA code)"
                  />
                </div>
                <div className="form-group">
                  <label>Notes</label>
                  <textarea
                    value={paymentData.notes}
                    onChange={(e) => setPaymentData({ ...paymentData, notes: e.target.value })}
                    rows="3"
                  />
                </div>
                <div className="slide-in-panel-footer">
                  <button type="button" onClick={() => setShowPaymentModal(false)} className="btn btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary">
                    Record Payment
                  </button>
                </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Invoice"
          message={`Are you sure you want to delete invoice ${selectedInvoice?.invoice_number}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedInvoice(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </div>
    </Layout>
  );
};

export default Invoices;

