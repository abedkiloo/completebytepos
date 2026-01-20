import React, { useState, useEffect } from 'react';
import { invoicesAPI, paymentsAPI, customersAPI, salesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Layout from '../Layout/Layout';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
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
  }, [searchQuery, statusFilter]);

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
      const response = await customersAPI.list({ is_active: 'true' });
      setCustomers(response.data.results || response.data || []);
    } catch (error) {
      console.error('Error loading customers:', error);
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

  const handleCreate = () => {
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
    });
    setShowModal(true);
  };

  const handleEdit = (invoice) => {
    setSelectedInvoice(invoice);
    
    // Format due_date to YYYY-MM-DD format if it exists
    let formattedDueDate = '';
    if (invoice.due_date) {
      const date = new Date(invoice.due_date);
      if (!isNaN(date.getTime())) {
        formattedDueDate = date.toISOString().split('T')[0];
      }
    }
    
    setFormData({
      customer_id: invoice.customer || '',
      customer_name: invoice.customer_name || '',
      customer_email: invoice.customer_email || '',
      customer_phone: invoice.customer_phone || '',
      customer_address: invoice.customer_address || '',
      subtotal: invoice.subtotal || 0,
      tax_amount: invoice.tax_amount || 0,
      discount_amount: invoice.discount_amount || 0,
      total: invoice.total || 0,
      due_date: formattedDueDate,
      notes: invoice.notes || '',
      status: invoice.status || 'draft',
    });
    setShowModal(true);
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
      const invoiceData = {
        ...formData,
        subtotal: parseFloat(formData.subtotal) || 0,
        tax_amount: parseFloat(formData.tax_amount) || 0,
        discount_amount: parseFloat(formData.discount_amount) || 0,
        total: parseFloat(formData.total) || 0,
        customer_id: formData.customer_id || null,
        due_date: formData.due_date || null,
        // Items should be provided when creating manually, or sale_id when creating from sale
        items: formData.items || [],
        sale_id: formData.sale_id || null,
      };
      
      // Validate that invoice has items when creating manually (not from sale)
      if (!selectedInvoice && !invoiceData.sale_id) {
        if (!invoiceData.items || invoiceData.items.length === 0) {
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

  const handleCustomerChange = (customerId) => {
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
    }
  };

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
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="status-filter"
          >
            <option value="all">All Status</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="partial">Partially Paid</option>
            <option value="paid">Paid</option>
            <option value="overdue">Overdue</option>
            <option value="cancelled">Cancelled</option>
          </select>
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
                  <select
                    value={formData.customer_id}
                    onChange={(e) => handleCustomerChange(e.target.value)}
                  >
                    <option value="">Select Customer</option>
                    {customers.map(customer => (
                      <option key={customer.id} value={customer.id}>
                        {customer.name} ({customer.customer_code})
                      </option>
                    ))}
                  </select>
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
                <div className="form-row">
                  <div className="form-group">
                    <label>Subtotal</label>
                    <input
                      type="number"
                      step="0.01"
                      value={formData.subtotal}
                      onChange={(e) => setFormData({ ...formData, subtotal: e.target.value })}
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
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  >
                    <option value="draft">Draft</option>
                    <option value="sent">Sent</option>
                    <option value="partial">Partially Paid</option>
                    <option value="paid">Paid</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
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
                    <select
                      value={paymentData.payment_method}
                      onChange={(e) => setPaymentData({ ...paymentData, payment_method: e.target.value })}
                      required
                    >
                      <option value="cash">Cash</option>
                      <option value="mpesa">M-PESA</option>
                      <option value="bank_transfer">Bank Transfer</option>
                      <option value="cheque">Cheque</option>
                      <option value="card">Card</option>
                      <option value="other">Other</option>
                    </select>
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

