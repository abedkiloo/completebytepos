import React, { useState, useEffect } from 'react';
import { Factory, Plus } from 'lucide-react';
import { suppliersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import SupplierForm from './SupplierForm';
import SearchableSelect from '../Shared/SearchableSelect';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  suppliersShowSupplierCode,
  suppliersShowSupplierType,
  suppliersShowContactDetails,
  suppliersShowPaymentTerms,
  suppliersShowCreditFields,
  suppliersShowRating,
  suppliersShowPreferredFlag,
  suppliersShowStatus,
  suppliersEnableCreate,
  suppliersEnableEdit,
  suppliersEnableDelete,
  suppliersShowNotes,
  suppliersShowBusinessDetails,
  suppliersEnableStatistics,
} from '../../utils/supplierDisplay';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  FilterBar,
  SearchField,
  FilterField,
  SummaryCard,
} from '../page';

const Suppliers = () => {
  const { settings: supplierSettings } = useModuleSettings('suppliers');
  const { settings: storeSettings } = useStoreSettings();

  const showSupplierCode = suppliersShowSupplierCode(supplierSettings);
  const showSupplierType = suppliersShowSupplierType(supplierSettings);
  const showContact = suppliersShowContactDetails(supplierSettings);
  const showPaymentTerms = suppliersShowPaymentTerms(supplierSettings);
  const showCredit = suppliersShowCreditFields(supplierSettings);
  const showRating = suppliersShowRating(supplierSettings);
  const showPreferred = suppliersShowPreferredFlag(supplierSettings);
  const showStatus = suppliersShowStatus(supplierSettings, storeSettings);
  const canCreate = suppliersEnableCreate(supplierSettings);
  const canEdit = suppliersEnableEdit(supplierSettings);
  const canDelete = suppliersEnableDelete(supplierSettings);
  const showStats = suppliersEnableStatistics(supplierSettings);

  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedSupplier, setSelectedSupplier] = useState(null);
  const [filters, setFilters] = useState({
    is_active: '',
    supplier_type: '',
    is_preferred: '',
  });
  const [statistics, setStatistics] = useState(null);

  useEffect(() => {
    loadSuppliers();
    loadStatistics();
  }, [searchQuery, filters]);

  const loadSuppliers = async () => {
    setLoading(true);
    try {
      const params = {};
      if (searchQuery) {
        params.search = searchQuery;
      }
      if (filters.is_active !== '') {
        params.is_active = filters.is_active;
      }
      if (filters.supplier_type) {
        params.supplier_type = filters.supplier_type;
      }
      if (filters.is_preferred !== '') {
        params.is_preferred = filters.is_preferred;
      }
      
      const response = await suppliersAPI.list(params);
      const suppliersData = response.data.results || response.data || [];
      setSuppliers(Array.isArray(suppliersData) ? suppliersData : []);
    } catch (error) {
      console.error('Error loading suppliers:', error);
      toast.error('Failed to load suppliers');
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    if (!showStats) {
      setStatistics(null);
      return;
    }
    try {
      const response = await suppliersAPI.statistics();
      setStatistics(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const handleCreate = () => {
    setSelectedSupplier(null);
    setShowForm(true);
  };

  const handleEdit = (supplier) => {
    setSelectedSupplier(supplier);
    setShowForm(true);
  };

  const handleDelete = (supplier) => {
    setSelectedSupplier(supplier);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedSupplier) return;
    
    try {
      await suppliersAPI.delete(selectedSupplier.id);
      toast.success('Supplier deleted successfully');
      loadSuppliers();
      loadStatistics();
      setShowDeleteConfirm(false);
      setSelectedSupplier(null);
    } catch (error) {
      toast.error('Failed to delete supplier: ' + (error.response?.data?.error || error.message));
      setShowDeleteConfirm(false);
    }
  };

  const handleSave = () => {
    loadSuppliers();
    loadStatistics();
    setShowForm(false);
    setSelectedSupplier(null);
  };

  const getSupplierTypeDisplay = (type) => {
    const types = {
      'individual': 'Individual',
      'business': 'Business',
      'manufacturer': 'Manufacturer',
      'distributor': 'Distributor',
      'wholesaler': 'Wholesaler',
    };
    return types[type] || type;
  };

  const getPaymentTermsDisplay = (terms) => {
    const termsMap = {
      'net_15': 'Net 15',
      'net_30': 'Net 30',
      'net_45': 'Net 45',
      'net_60': 'Net 60',
      'cod': 'Cash on Delivery',
      'prepaid': 'Prepaid',
      'custom': 'Custom Terms',
    };
    return termsMap[terms] || terms;
  };

  if (loading && suppliers.length === 0) {
    return (
      <PageLoading rows={6} showStats />
    );
  }

  return (
    <PageShell>
        <PageHeader title="Suppliers" description="Vendors you buy stock from.">
          {canCreate && (
            <Button onClick={handleCreate}>
              <Plus className="h-4 w-4" />
              Add supplier
            </Button>
          )}
        </PageHeader>

        {showStats && statistics && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard icon={Factory} label="Total" value={statistics.total_suppliers || 0} />
            {showStatus && (
              <SummaryCard icon={Factory} label="Active" value={statistics.active_suppliers || 0} tone="success" />
            )}
            {showPreferred && (
              <SummaryCard icon={Factory} label="Preferred" value={statistics.preferred_suppliers || 0} />
            )}
            {showCredit && (
              <SummaryCard
                icon={Factory}
                label="Account balance"
                value={formatCurrency(statistics.total_account_balance || 0)}
              />
            )}
          </div>
        )}

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search suppliers…"
            className="min-w-[200px] flex-[2]"
          />
          <FilterField label="Status">
            {showStatus ? (
            <SearchableSelect
              value={filters.is_active}
              onChange={(e) => setFilters({ ...filters, is_active: e.target.value })}
              options={[
                { id: '', name: 'All status' },
                { id: 'true', name: 'Active' },
                { id: 'false', name: 'Inactive' },
              ]}
              placeholder="All status"
            />
            ) : null}
          </FilterField>
          {showSupplierType && (
          <FilterField label="Type">
            <SearchableSelect
              value={filters.supplier_type}
              onChange={(e) => setFilters({ ...filters, supplier_type: e.target.value })}
              options={[
                { id: '', name: 'All types' },
                { id: 'individual', name: 'Individual' },
                { id: 'business', name: 'Business' },
                { id: 'manufacturer', name: 'Manufacturer' },
                { id: 'distributor', name: 'Distributor' },
                { id: 'wholesaler', name: 'Wholesaler' },
              ]}
              placeholder="All types"
            />
          </FilterField>
          )}
        </FilterBar>

        {suppliers.length === 0 ? (
          <EmptyState
            icon={Factory}
            title="No suppliers"
            description="Add vendors you purchase inventory from."
            actionLabel={canCreate ? 'Add supplier' : undefined}
            onAction={canCreate ? handleCreate : undefined}
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  {showSupplierCode && <th>Code</th>}
                  <th>Name</th>
                  {showSupplierType && <th>Type</th>}
                  {showContact && <th>Contact Person</th>}
                  {showContact && <th>Email</th>}
                  {showContact && <th>Phone</th>}
                  {showContact && <th>City</th>}
                  {showPaymentTerms && <th>Payment Terms</th>}
                  {showCredit && <th>Credit Limit</th>}
                  {showCredit && <th>Account Balance</th>}
                  {showRating && <th>Rating</th>}
                  {showStatus && <th>Status</th>}
                  {(canEdit || canDelete) && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {suppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    {showSupplierCode && <td>{supplier.supplier_code}</td>}
                    <td>
                      <div className="supplier-name-cell">
                        <strong>{supplier.name}</strong>
                        {showPreferred && supplier.is_preferred && (
                          <span className="badge preferred">Preferred</span>
                        )}
                      </div>
                    </td>
                    {showSupplierType && <td>{getSupplierTypeDisplay(supplier.supplier_type)}</td>}
                    {showContact && <td>{supplier.contact_person || '-'}</td>}
                    {showContact && <td>{supplier.email || '-'}</td>}
                    {showContact && <td>{supplier.phone || '-'}</td>}
                    {showContact && <td>{supplier.city || '-'}</td>}
                    {showPaymentTerms && <td>{getPaymentTermsDisplay(supplier.payment_terms)}</td>}
                    {showCredit && <td>{formatCurrency(supplier.credit_limit || 0)}</td>}
                    {showCredit && (
                      <td>
                        <span className={supplier.account_balance > 0 ? 'balance-owed' : ''}>
                          {formatCurrency(supplier.account_balance || 0)}
                        </span>
                      </td>
                    )}
                    {showRating && (
                      <td>
                        <div className="rating-stars">
                          {'★'.repeat(supplier.rating || 0)}
                          {'☆'.repeat(5 - (supplier.rating || 0))}
                        </div>
                      </td>
                    )}
                    {showStatus && (
                      <td>
                        <span className={`status-badge ${supplier.is_active ? 'active' : 'inactive'}`}>
                          {supplier.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    )}
                    {(canEdit || canDelete) && (
                      <td>
                        <div className="action-buttons">
                          {canEdit && (
                            <button onClick={() => handleEdit(supplier)} className="btn-edit">Edit</button>
                          )}
                          {canDelete && (
                            <button onClick={() => handleDelete(supplier)} className="btn-delete">Delete</button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Supplier Form */}
        {showForm && (
          <SupplierForm
            supplier={selectedSupplier}
            onClose={() => {
              setShowForm(false);
              setSelectedSupplier(null);
            }}
            onSave={handleSave}
            showSupplierType={showSupplierType}
            showContactDetails={showContact}
            showBusinessDetails={suppliersShowBusinessDetails(supplierSettings)}
            showPaymentTerms={showPaymentTerms}
            showCreditFields={showCredit}
            showNotes={suppliersShowNotes(supplierSettings)}
            showRating={showRating}
            showPreferred={showPreferred}
            showStatus={showStatus}
          />
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Supplier"
          message={`Are you sure you want to delete ${selectedSupplier?.name}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedSupplier(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
      </PageShell>
  );
};

export default Suppliers;
