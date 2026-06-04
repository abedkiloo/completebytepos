import React, { useState, useEffect } from 'react';
import { invoicesAPI, paymentsAPI, customersAPI, salesAPI, productsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { PageShell, PageHeader, PageLoading, EmptyState, FilterBar, SearchField, FilterPills } from '../page';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Plus, FileText } from 'lucide-react';
import {
  formatInvoiceItemsForApi,
  formatPaymentPayload,
  parseInvoiceBalance,
  validatePaymentAmount,
} from '../../utils/invoicePayload';
import {
  invoiceCreationAllowed,
  invoiceTrackingAllowed,
  paymentTrackingAllowed,
} from '../../utils/invoicingAccess';

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

  const canCreateInvoice = invoiceCreationAllowed();
  const canRecordPayment = paymentTrackingAllowed();
  const canSendInvoice = invoiceTrackingAllowed();

  const handleCreate = async () => {
    if (!canCreateInvoice) {
      toast.error('Invoice creation is disabled in module settings.');
      return;
    }
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

  const handleDownloadPdf = async (invoice) => {
    try {
      await invoicesAPI.downloadPDF(invoice.id, invoice.invoice_number);
      toast.success('Invoice PDF downloaded');
    } catch (error) {
      toast.error(error.message || 'Failed to download PDF');
    }
  };

  const handleSendInvoice = async (invoice) => {
    if (!canSendInvoice) {
      toast.error('Sending invoices is disabled in module settings.');
      return;
    }
    try {
      await invoicesAPI.send(invoice.id);
      toast.success('Invoice sent — receivable recorded in accounting.');
      loadInvoices();
    } catch (error) {
      toast.error('Failed to send invoice: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleAddPayment = (invoice) => {
    if (!canRecordPayment) {
      toast.error('Recording payments is disabled in module settings.');
      return;
    }
    setSelectedInvoice(invoice);
    setPaymentData({
      amount: '',
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

    if (!selectedInvoice && !canCreateInvoice) {
      toast.error('Invoice creation is disabled in module settings.');
      return;
    }

    try {
      // Format items for API - only include items with product_id
      const formattedItems = formatInvoiceItemsForApi(formData.items);
      
      const { status: _status, ...formWithoutStatus } = formData;
      const invoiceData = {
        ...formWithoutStatus,
        subtotal: parseFloat(formData.subtotal) || 0,
        tax_amount: parseFloat(formData.tax_amount) || 0,
        discount_amount: parseFloat(formData.discount_amount) || 0,
        total: parseFloat(formData.total) || 0,
        customer_id: formData.customer_id || null,
        due_date: formData.due_date || null,
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
      const quantity = parseInt(item.quantity) || 0;
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
      
      // Normalize quantity to integer if it's the quantity field (allow 0 to remove/zero line)
      if (field === 'quantity') {
        const qtyValue = value.toString().trim();
        let normalizedQty;
        
        if (qtyValue === '' || qtyValue === '-') {
          normalizedQty = ''; // Allow empty during typing
        } else if (qtyValue.includes('.')) {
          const parsed = Math.floor(parseFloat(qtyValue));
          normalizedQty = isNaN(parsed) ? '' : Math.max(0, parsed);
        } else {
          const parsed = parseInt(qtyValue, 10);
          normalizedQty = (qtyValue === '' || isNaN(parsed)) ? '' : Math.max(0, parsed);
        }
        
        newItems[index] = {
          ...newItems[index],
          [field]: normalizedQty,
        };
      } else {
        newItems[index] = {
          ...newItems[index],
          [field]: value,
        };
      }
      
      // Auto-calculate subtotal for this item
      if (field === 'quantity' || field === 'unit_price') {
        // Use parseInt for quantity (whole numbers only) and parseFloat for unit_price
        const quantity = parseInt(newItems[index].quantity) || 0;
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
      if (!paymentTrackingAllowed()) {
        toast.error('Recording payments is disabled in module settings.');
        return;
      }

      const validation = validatePaymentAmount(paymentData.amount, selectedInvoice);
      if (!validation.ok) {
        toast.error(validation.error);
        return;
      }

      const paymentPayload = formatPaymentPayload({
        invoiceId: selectedInvoice.id,
        amount: validation.amount,
        payment_method: paymentData.payment_method,
        payment_date: paymentData.payment_date,
        reference: paymentData.reference,
        notes: paymentData.notes,
      });

      await paymentsAPI.create(paymentPayload);
      const balanceAfter = parseInvoiceBalance(selectedInvoice) - validation.amount;
      const msg =
        balanceAfter > 0.01
          ? `Partial payment recorded. Remaining balance: ${formatCurrency(balanceAfter)}`
          : 'Payment recorded — invoice fully settled.';
      toast.success(msg);
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

  const statusOptions = [
    { value: 'all', label: 'All' },
    { value: 'draft', label: 'Draft' },
    { value: 'sent', label: 'Sent' },
    { value: 'partial', label: 'Partial' },
    { value: 'paid', label: 'Paid' },
    { value: 'overdue', label: 'Overdue' },
    { value: 'cancelled', label: 'Cancelled' },
  ];

  return (
    <PageShell>
        <PageHeader title="Invoices" description="Create invoices and track payments.">
          {canCreateInvoice ? (
            <Button onClick={handleCreate}>
              <Plus className="h-4 w-4" />
              Create invoice
            </Button>
          ) : null}
        </PageHeader>

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search invoices…"
            className="min-w-[200px] flex-[2]"
          />
          <SearchableSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={statusOptions.map((o) => ({ id: o.value, name: o.label }))}
            placeholder="Status"
          />
        </FilterBar>

        {loading ? (
          <PageLoading rows={6} />
        ) : invoices.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No invoices"
            description="Create an invoice from a sale or manually."
            actionLabel={canCreateInvoice ? 'Create invoice' : undefined}
            onAction={canCreateInvoice ? handleCreate : undefined}
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">Invoice #</th>
                  <th className="px-3 py-2 font-medium">Customer</th>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Due date</th>
                  <th className="px-3 py-2 font-medium">Total</th>
                  <th className="px-3 py-2 font-medium">Paid</th>
                  <th className="px-3 py-2 font-medium">Balance</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-3 py-2 font-medium">{invoice.invoice_number}</td>
                    <td className="px-3 py-2">
                      <div>{invoice.customer_name || invoice.customer_detail?.name || 'N/A'}</div>
                      {invoice.customer_email ? (
                        <div className="text-xs text-muted-foreground">{invoice.customer_email}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{new Date(invoice.created_at).toLocaleDateString()}</td>
                    <td className="px-3 py-2">
                      {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-3 py-2">{formatCurrency(invoice.total)}</td>
                    <td className="px-3 py-2">{formatCurrency(invoice.amount_paid || 0)}</td>
                    <td className="px-3 py-2">
                      <span className={invoice.balance > 0 ? 'font-medium text-amber-700' : 'text-emerald-700'}>
                        {formatCurrency(invoice.balance || 0)}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="secondary" className="capitalize">
                        {invoice.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap justify-end gap-1">
                        <Button type="button" variant="outline" size="sm" onClick={() => handleEdit(invoice)}>
                          View
                        </Button>
                        {invoice.status === 'draft' && canSendInvoice ? (
                          <Button type="button" size="sm" variant="secondary" onClick={() => handleSendInvoice(invoice)}>
                            Send
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownloadPdf(invoice)}
                        >
                          PDF
                        </Button>
                        {invoice.balance > 0 && canRecordPayment ? (
                          <Button type="button" size="sm" onClick={() => handleAddPayment(invoice)}>
                            Payment
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(invoice)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
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
                {/* Invoice Items Management - Editable when creating/editing */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <label>Invoice Items</label>
                    <Button type="button" size="sm" onClick={handleAddItem}>
                      + Add Item
                    </Button>
                  </div>
                  
                  {formData.items && formData.items.length > 0 ? (
                    <div className="mt-2 overflow-hidden rounded-lg border bg-card">
                      <table className="w-full text-sm">
                        <thead className="border-b bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2">Product</th>
                            <th className="px-3 py-2 text-right">Qty</th>
                            <th className="px-3 py-2 text-right">Unit Price</th>
                            <th className="px-3 py-2 text-right">Subtotal</th>
                            <th className="px-3 py-2 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {formData.items.map((item, idx) => {
                            const productOptions = products.map(p => ({
                              id: p.id,
                              name: `${p.name}${p.sku ? ` (${p.sku})` : ''}`,
                            }));
                            
                            return (
                              <tr key={idx} className="border-b last:border-0">
                                <td className="px-3 py-2">
                                  <SearchableSelect
                                    value={item.product_id || ''}
                                    onChange={(e) => handleItemProductChange(idx, e.target.value)}
                                    options={productOptions}
                                    placeholder="Select Product"
                                  />
                                </td>
                                <td className="px-3 py-2 text-right">
                                  <input
                                    type="number"
                                    min="0"
                                    step="1"
                                    value={item.quantity ?? ''}
                                    onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)}
                                    onBlur={(e) => {
                                      const value = parseInt(e.target.value, 10);
                                      if (isNaN(value) || value < 0) {
                                        handleItemChange(idx, 'quantity', '0');
                                      }
                                    }}
                                    className="w-20 rounded-md border px-2 py-1 text-right"
                                  />
                                </td>
                                <td className="px-3 py-2 text-right">
                                  <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={item.unit_price || ''}
                                    onChange={(e) => handleItemChange(idx, 'unit_price', e.target.value)}
                                    className="w-24 rounded-md border px-2 py-1 text-right"
                                  />
                                </td>
                                <td className="px-3 py-2 text-right font-semibold tabular-nums">
                                  {formatCurrency(item.subtotal || 0)}
                                </td>
                                <td className="px-3 py-2 text-right">
                                  <Button
                                    type="button"
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => handleRemoveItem(idx)}
                                  >
                                    Remove
                                  </Button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground">
                      No items added. Click &quot;Add Item&quot; to add products to this invoice.
                    </div>
                  )}
                </div>

                {/* Invoice Items Display - Read-only when viewing existing invoice */}
                {selectedInvoice && selectedInvoice.items && selectedInvoice.items.length > 0 && (
                  <div className="form-group">
                    <label>Invoice Items</label>
                    <div className="mt-2 overflow-hidden rounded-lg border bg-card">
                      <table className="w-full text-sm">
                        <thead className="border-b bg-muted/40 text-left text-xs font-medium text-muted-foreground">
                          <tr>
                            <th className="px-3 py-2">Item</th>
                            <th className="px-3 py-2 text-right">Qty</th>
                            <th className="px-3 py-2 text-right">Unit Price</th>
                            <th className="px-3 py-2 text-right">Subtotal</th>
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
                              <tr key={item.id || idx} className="border-b last:border-0">
                                <td className="px-3 py-2">
                                  <div className="font-medium">{displayName}</div>
                                  {item.product_sku && (
                                    <div className="text-xs text-muted-foreground">SKU: {item.product_sku}</div>
                                  )}
                                  {item.description && (
                                    <div className="text-xs italic text-muted-foreground">{item.description}</div>
                                  )}
                                </td>
                                <td className="px-3 py-2 text-right">{item.quantity}</td>
                                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(item.unit_price)}</td>
                                <td className="px-3 py-2 text-right font-semibold tabular-nums">{formatCurrency(item.subtotal)}</td>
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
                {selectedInvoice ? (
                  <div className="form-group">
                    <label>Status</label>
                    <input
                      type="text"
                      value={formData.status}
                      readOnly
                      className="readonly capitalize"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Use Send on the list to recognize receivables. Record payments to settle.
                    </p>
                  </div>
                ) : null}

                {/* Address - Smaller field below invoice items, above notes */}
                <div className="form-group">
                  <label>Address</label>
                  <input
                    type="text"
                    value={formData.customer_address}
                    onChange={(e) => setFormData({ ...formData, customer_address: e.target.value })}
                    placeholder="Customer address"
                    style={{ fontSize: '0.875rem', padding: '0.5rem' }}
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
                  <Button type="button" variant="outline" onClick={() => setShowModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">
                    {selectedInvoice ? 'Update' : 'Create'}
                  </Button>
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
                <div className="mb-4 space-y-1 rounded-lg border bg-muted/30 p-4 text-sm">
                  <p><strong>Invoice:</strong> {selectedInvoice.invoice_number}</p>
                  <p><strong>Total:</strong> {formatCurrency(selectedInvoice.total)}</p>
                  <p><strong>Paid:</strong> {formatCurrency(selectedInvoice.amount_paid || 0)}</p>
                  <p><strong>Balance:</strong> {formatCurrency(selectedInvoice.balance || 0)}</p>
                </div>
                <form onSubmit={handlePaymentSubmit}>
                <div className="form-group">
                  <label>Payment amount *</label>
                  <div className="flex flex-wrap gap-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={paymentData.amount}
                      onChange={(e) => setPaymentData({ ...paymentData, amount: e.target.value })}
                      placeholder="Enter amount (partial or full)"
                      className="min-w-[12rem] flex-1"
                      required
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setPaymentData({
                          ...paymentData,
                          amount: String(parseInvoiceBalance(selectedInvoice)),
                        })
                      }
                    >
                      Pay full balance
                    </Button>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    You can pay any amount up to the remaining balance. Leave blank and enter a
                    partial amount, or use Pay full balance to settle in one step.
                  </p>
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
                  <Button type="button" variant="outline" onClick={() => setShowPaymentModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">
                    Record Payment
                  </Button>
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
      </PageShell>
  );
};

export default Invoices;

