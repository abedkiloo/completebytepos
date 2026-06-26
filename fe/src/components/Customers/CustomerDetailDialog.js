import React, { useCallback, useState } from 'react';
import { Mail, MapPin, Phone, Wallet } from 'lucide-react';
import { salesAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { toast } from '../../utils/toast';
import { getStoredAuth, isManagerOrAdminFromStorage } from '../../utils/roleAccess';
import { userCanRefundSales, handleSaleRefundResponse } from '../../utils/saleRefund';
import { pendingApprovalToastMessage } from '../../utils/makerChecker';
import { getWalletDebtAmount } from '../../utils/walletDisplay';
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
import ReceiveWalletPaymentDialog from './ReceiveWalletPaymentDialog';

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
  const [walletPaymentOpen, setWalletPaymentOpen] = useState(false);

  const { permissions } = getStoredAuth();
  const canRefund = userCanRefundSales(permissions, {
    isManagerOrAdmin: isManagerOrAdminFromStorage(),
  });

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

  const handleDialogChange = (next) => {
    if (!next) {
      setSelectedSale(null);
      setSaleDetailOpen(false);
      setRefundSale(null);
    }
    onOpenChange(next);
  };

  if (!customer) return null;

  const outstanding = parseFloat(customer.total_outstanding || 0);
  const walletDebt = getWalletDebtAmount(customer.wallet_balance);

  return (
    <>
      <Dialog open={open} onOpenChange={handleDialogChange}>
        <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
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
                {customer.city ? (
                  <p className="inline-flex items-center gap-1.5 text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    {[customer.city, customer.country].filter(Boolean).join(', ')}
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
        onRefund={openRefundDialog}
        showCustomerName={false}
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

      <ReceiveWalletPaymentDialog
        open={walletPaymentOpen}
        customer={customer}
        onOpenChange={setWalletPaymentOpen}
        onSuccess={(updated) => {
          onCustomerUpdated?.(updated);
          setWalletPaymentOpen(false);
        }}
      />
    </>
  );
}
