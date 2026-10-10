import React, { useCallback, useState } from 'react';
import { Mail, MapPin, Pencil, Phone, Wallet } from 'lucide-react';
import { customersAPI, salesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { userCanRefundSales, userCanRollbackSales, handleSaleRefundResponse } from '../../utils/saleRefund';
import { userHasAdminSaleOverride } from '../../utils/saleCompletionApproval';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
import { dispatchNavBadgesRefresh } from '../../utils/navBadges';
import { customerCommitRows } from '../../utils/formCommitSummary';
import {
  EMPTY_CUSTOMER_FORM,
  customerFormBackendErrors,
  customerFormFromRecord,
  customerSavePayload,
  validateCustomerForm,
} from '../../utils/customerFormState';
import {
  customersEnableEdit,
  customersShowCustomerType,
  customersShowNotes,
  customersShowStatus,
  customersShowTaxId,
} from '../../utils/customerDisplay';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { CustomerWalletBalance } from './CustomerWalletBalance';
import CustomerSalesList from './CustomerSalesList';
import SaleDetailDialog from '../Sales/SaleDetailDialog';
import RefundSaleDialog from '../Sales/RefundSaleDialog';
import SaleRollbackDialog from '../Sales/SaleRollbackDialog';
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';
import CustomerFormDialog from './CustomerFormDialog';
import CommitConfirm from '../Shared/CommitConfirm';
import CenterScreenLoader from '../Shared/CenterScreenLoader';

export default function CustomerDetailDialog({
  customer,
  open,
  onOpenChange,
  showOutstanding = true,
  showWallet = true,
  canRecordWalletPayment = false,
  onCustomerUpdated,
}) {
  const [selectedSale, setSelectedSale] = useState(null);
  const [saleDetailOpen, setSaleDetailOpen] = useState(false);
  const [refundSale, setRefundSale] = useState(null);
  const [refundSubmitting, setRefundSubmitting] = useState(false);
  const [rollbackSale, setRollbackSale] = useState(null);
  const [rollbackSubmitting, setRollbackSubmitting] = useState(false);
  const [walletPaymentOpen, setWalletPaymentOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [formData, setFormData] = useState(EMPTY_CUSTOMER_FORM);
  const [formErrors, setFormErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);

  const { permissions } = getStoredAuth();
  const { settings: customerModuleSettings } = useModuleSettings('customers');
  const { settings: storeSettings } = useStoreSettings();
  const canEdit = customersEnableEdit(customerModuleSettings);
  const showCustomerType = customersShowCustomerType(customerModuleSettings);
  const showTaxId = customersShowTaxId(customerModuleSettings);
  const showNotes = customersShowNotes(customerModuleSettings);
  const showStatus = customersShowStatus(customerModuleSettings, storeSettings);
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });
  const canRollback = userCanRollbackSales(permissions);
  const canReturnForCorrection = userHasAdminSaleOverride();

  const handleSelectSale = useCallback(async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setSelectedSale(response.data);
      setSaleDetailOpen(true);
    } catch (error) {
      toast.error(
        'Failed to load sale: ' + (error.response?.data?.error || error.message)
      );
    }
  }, []);

  const openRefundDialog = useCallback(async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setSaleDetailOpen(false);
      setRefundSale(response.data);
    } catch (error) {
      toast.error(
        'Failed to load sale: ' + (error.response?.data?.error || error.message)
      );
    }
  }, []);

  const openRollbackDialog = useCallback(async (sale) => {
    try {
      const response = await salesAPI.get(sale.id);
      setSaleDetailOpen(false);
      setRollbackSale(response.data);
    } catch (error) {
      toast.error(
        'Failed to load sale: ' + (error.response?.data?.error || error.message)
      );
    }
  }, []);

  const handleRefundSubmit = async (payload) => {
    if (!refundSale) return;
    setRefundSubmitting(true);
    try {
      const res = await salesAPI.refund(refundSale.id, payload);
      handleSaleRefundResponse(res, {
        onApplied: async (data) => {
          toast.success(`Void recorded as ${data.refund_number}`);
          if (selectedSale?.id === refundSale.id) {
            const refreshed = await salesAPI.get(refundSale.id);
            setSelectedSale(refreshed.data);
          }
        },
        onPending: () => toast.success(pendingApprovalToastMessage()),
      });
      setRefundSale(null);
      onCustomerUpdated?.();
    } catch (error) {
      const data = error.response?.data;
      const msg =
        data?.reason?.[0] ||
        data?.items?.[0] ||
        data?.error ||
        data?.detail ||
        error.message;
      toast.error(typeof msg === 'string' ? msg : 'Refund failed');
    } finally {
      setRefundSubmitting(false);
    }
  };

  const handleRollbackSubmit = async (payload) => {
    if (!rollbackSale) return;
    setRollbackSubmitting(true);
    try {
      const res = await salesAPI.rollback(rollbackSale.id, payload);
      handleSaleRefundResponse(res, {
        onApplied: async (data) => {
          toast.success(`Sale rolled back as ${data.refund_number}`);
          if (selectedSale?.id === rollbackSale.id) {
            const refreshed = await salesAPI.get(rollbackSale.id);
            setSelectedSale(refreshed.data);
          }
        },
        onPending: () => toast.success(pendingApprovalToastMessage()),
      });
      setRollbackSale(null);
      onCustomerUpdated?.();
    } catch (error) {
      const data = error.response?.data;
      const msg = data?.reason?.[0] || data?.error || data?.detail || error.message;
      toast.error(typeof msg === 'string' ? msg : 'Rollback failed');
    } finally {
      setRollbackSubmitting(false);
    }
  };

  const handleDialogChange = (next) => {
    if (!next) {
      setSelectedSale(null);
      setSaleDetailOpen(false);
      setRefundSale(null);
      setRollbackSale(null);
    }
    onOpenChange(next);
  };

  const openEdit = async () => {
    setFormData(customerFormFromRecord(customer));
    setFormErrors({});
    setEditOpen(true);
    try {
      const res = await customersAPI.get(customer.id);
      setFormData(customerFormFromRecord(res.data));
    } catch (_err) {
      // Keep the customer already shown if the full record cannot load.
    }
  };

  const updateField = (key, value) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
    if (formErrors[key]) {
      setFormErrors((prev) => ({ ...prev, [key]: '' }));
    }
  };

  const handleEditSubmit = (e) => {
    e?.preventDefault?.();
    const errors = validateCustomerForm(formData);
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error(Object.values(errors)[0]);
      return;
    }
    setShowCommitConfirm(true);
  };

  const confirmEdit = async () => {
    if (saving || !customer) return;
    setSaving(true);
    try {
      const res = await customersAPI.update(customer.id, customerSavePayload(formData));
      toast.success('Duka updated');
      setShowCommitConfirm(false);
      setEditOpen(false);
      onCustomerUpdated?.(res.data);
    } catch (error) {
      const data = error.response?.data;
      const backendErrors = customerFormBackendErrors(data);
      if (backendErrors) {
        setFormErrors(backendErrors);
        toast.error(Object.values(backendErrors)[0] || 'Failed to save customer');
      } else {
        toast.error(data?.error || data?.detail || error.message || 'Failed to save customer');
      }
    } finally {
      setSaving(false);
    }
  };

  if (!customer) return null;

  const outstanding = parseFloat(customer.total_outstanding || 0);
  const walletDebt = getWalletDebtAmount(customer.wallet_balance);

  return (
    <>
      <Dialog open={open} onOpenChange={handleDialogChange}>
        <DialogContent
          className="max-h-[92vh] max-w-2xl overflow-y-auto"
          description={`Profile, contact details, and sales for ${customer.name}.`}
        >
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">
              {customer.name}
              {customer.customer_code ? (
                <span className="font-mono text-sm font-normal text-muted-foreground">
                  {customer.customer_code}
                </span>
              ) : null}
              {customer.customer_type === 'business' ? (
                <Badge variant="secondary">Business</Badge>
              ) : null}
              {canEdit ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="ml-auto"
                  onClick={openEdit}
                >
                  <Pencil className="mr-1 h-3.5 w-3.5" />
                  Edit
                </Button>
              ) : null}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            <section className="grid gap-3 rounded-lg border bg-muted/20 p-4 text-sm sm:grid-cols-2">
              <div className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Contact
                </p>
                {customer.email ? (
                  <p className="inline-flex items-center gap-1.5">
                    <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                    {customer.email}
                  </p>
                ) : null}
                {customer.phone ? (
                  <p className="inline-flex items-center gap-1.5">
                    <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                    {customer.phone}
                  </p>
                ) : null}
                {customer.ward || customer.sub_county || customer.county || customer.city ? (
                  <p className="inline-flex items-center gap-1.5 text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    {[
                      [customer.ward, customer.sub_county, customer.county || customer.city]
                        .filter(Boolean)
                        .join(', '),
                      customer.country,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                ) : null}
              </div>
              <div className="space-y-2">
                {showOutstanding ? (
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Invoice balance</span>
                    <span
                      className={
                        outstanding > 0 ? 'font-semibold text-destructive' : 'text-muted-foreground'
                      }
                    >
                      {formatCurrency(outstanding)}
                    </span>
                  </div>
                ) : null}
                {showWallet ? (
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      <Wallet className="h-3.5 w-3.5" />
                      Wallet
                    </span>
                    <CustomerWalletBalance balance={customer.wallet_balance} />
                  </div>
                ) : null}
                {canRecordWalletPayment && showWallet && walletDebt > 0 ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => setWalletPaymentOpen(true)}
                  >
                    Receive wallet payment
                  </Button>
                ) : null}
              </div>
            </section>

            <CustomerSalesList customerId={customer.id} onSelectSale={handleSelectSale} />
          </div>
        </DialogContent>
      </Dialog>

      <SaleDetailDialog
        sale={selectedSale}
        open={saleDetailOpen}
        onOpenChange={setSaleDetailOpen}
        canRefund={canRefund}
        canRollback={canRollback}
        canReturnForCorrection={canReturnForCorrection}
        onReturned={() => {
          setSaleDetailOpen(false);
        }}
        onRefund={openRefundDialog}
        onRollback={openRollbackDialog}
        showCustomerName={false}
        showAdminDetails={canRefund || canRollback}
        onUpdated={(updated) => setSelectedSale(updated)}
      />

      <RefundSaleDialog
        sale={refundSale}
        open={Boolean(refundSale)}
        onOpenChange={(next) => {
          if (!next) setRefundSale(null);
        }}
        onSubmit={handleRefundSubmit}
        submitting={refundSubmitting}
      />

      <SaleRollbackDialog
        sale={rollbackSale}
        open={Boolean(rollbackSale)}
        onOpenChange={(next) => {
          if (!next) setRollbackSale(null);
        }}
        onSubmit={handleRollbackSubmit}
        submitting={rollbackSubmitting}
      />

      <CenterScreenLoader
        open={refundSubmitting || rollbackSubmitting}
        label={
          refundSubmitting
            ? 'Submitting void…'
            : rollbackSubmitting
              ? 'Submitting rollback…'
              : 'Loading…'
        }
      />

      <ReceiveWalletPaymentDialog
        open={walletPaymentOpen}
        customer={customer}
        onOpenChange={setWalletPaymentOpen}
        onSuccess={(updated) => {
          onCustomerUpdated?.(updated);
          setWalletPaymentOpen(false);
          dispatchNavBadgesRefresh();
        }}
      />

      <CustomerFormDialog
        open={editOpen}
        onOpenChange={(next) => {
          if (saving) return;
          setEditOpen(next);
          if (!next) setShowCommitConfirm(false);
        }}
        editing={customer}
        formData={formData}
        formErrors={formErrors}
        onChange={updateField}
        onSubmit={handleEditSubmit}
        saving={saving}
        showCustomerType={showCustomerType}
        showTaxId={showTaxId}
        showNotes={showNotes}
        showStatus={showStatus}
      />
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(open) => {
          if (!open && !saving) setShowCommitConfirm(false);
        }}
        title="Update this duka?"
        description="Review the customer details, then confirm to save."
        rows={customerCommitRows(formData, { isEdit: true })}
        submitting={saving}
        confirmText="Confirm & update"
        onConfirm={confirmEdit}
      />
    </>
  );
}
