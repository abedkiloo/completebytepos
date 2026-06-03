import React, { useEffect, useState, useRef } from 'react';
import { Printer, Mail, Check, Loader2, Receipt as ReceiptIcon, UserPlus } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { toast } from '../../../utils/toast';
import { formatCurrency } from '../../../utils/formatters';
import { isManagerOrAdminFromStorage } from '../../../utils/roleAccess';
import { useModuleSettings } from '../../../hooks/useModuleSettings';
import { canQuickAddCustomerAtPos } from '../../../utils/customerDisplay';
import CustomerFormModal from '../../Customers/CustomerFormModal';

import { ThermalReceipt } from './ThermalReceipt';
import { printThermalReceipt } from './printReceipt';
import { useStoreInfo } from './useStoreInfo';
import './ThermalReceipt.css';

function WhatsAppIcon({ className }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.435 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function customerDisplayName(sale) {
  return (
    sale?.customer_name ||
    sale?.customer?.name ||
    'Walk-in'
  );
}

function isWalkInSale(sale) {
  const name = customerDisplayName(sale).toLowerCase();
  return !sale?.customer_id || name.includes('walk-in');
}

function buildWhatsAppMessage(sale) {
  const lines = [
    `Receipt ${sale.sale_number || ''}`.trim(),
    `Total: ${formatCurrency(sale.total)}`,
    '',
    'Thank you for your purchase!',
  ];
  return lines.filter(Boolean).join('\n');
}

/**
 * Receipt preview with Print, Email, and WhatsApp actions.
 */
export default function ReceiptDialog({
  sale,
  open,
  onOpenChange,
  autoPrint = false,
}) {
  const store = useStoreInfo(sale);
  const { settings: customerModuleSettings } = useModuleSettings('customers');
  const [printing, setPrinting] = useState(false);
  const [printedOnce, setPrintedOnce] = useState(false);
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const autoPrintFiredFor = useRef(null);

  const doPrint = async () => {
    if (!sale || printing) return;
    setPrinting(true);
    try {
      const ok = await printThermalReceipt({ sale, store });
      if (ok) {
        setPrintedOnce(true);
      } else {
        toast.error('Could not open the print dialog. Check pop-up settings.');
      }
    } finally {
      setPrinting(false);
    }
  };

  useEffect(() => {
    if (!open || !autoPrint || !sale?.id) return;
    if (autoPrintFiredFor.current === sale.id) return;
    autoPrintFiredFor.current = sale.id;
    doPrint();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, autoPrint, sale?.id]);

  if (!sale) return null;

  const customerName = customerDisplayName(sale);
  const walkIn = isWalkInSale(sale);
  const canAddCustomer = canQuickAddCustomerAtPos(
    isManagerOrAdminFromStorage(),
    customerModuleSettings
  );

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="left-[50%] top-[3vh] flex max-h-[94dvh] w-[calc(100%-1rem)] max-w-[380px] translate-x-[-50%] translate-y-0 flex-col gap-0 overflow-hidden p-0 sm:max-w-[380px]"
          description={`Receipt for sale ${sale.sale_number}. Print, email, or send via WhatsApp.`}
        >
          <DialogHeader className="shrink-0 border-b px-3 py-2.5">
            <DialogTitle className="flex items-center gap-2 text-base">
              <ReceiptIcon className="h-5 w-5 text-primary" />
              Receipt
              <span className="text-xs font-normal text-muted-foreground">
                {sale.sale_number}
              </span>
              {printedOnce && (
                <span className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-success">
                  <Check className="h-3.5 w-3.5" />
                  Printed
                </span>
              )}
            </DialogTitle>
          </DialogHeader>

          <div className="flex shrink-0 items-center justify-between gap-2 border-b bg-muted/20 px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              {walkIn ? (
                <Badge variant="secondary" className="shrink-0 font-medium">
                  Walk-in
                </Badge>
              ) : (
                <Badge variant="outline" className="shrink-0 font-medium">
                  Customer
                </Badge>
              )}
              <span className="truncate text-sm font-semibold text-foreground">
                {customerName}
              </span>
            </div>
            {canAddCustomer && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 shrink-0 gap-1"
                onClick={() => setShowCustomerForm(true)}
              >
                <UserPlus className="h-3.5 w-3.5" />
                New Customer
              </Button>
            )}
          </div>

          <div
            className="receipt-dialog-scroll min-h-0 max-h-[calc(94dvh-10.5rem)] flex-1 overflow-y-auto overscroll-contain bg-muted/20 px-1 py-1.5"
            role="region"
            aria-label="Receipt preview"
          >
            <div className="w-full rounded-sm bg-white shadow-sm ring-1 ring-border print:shadow-none print:ring-0">
              <ThermalReceipt sale={sale} store={store} compact />
            </div>
          </div>

          <DialogFooter className="shrink-0 grid grid-cols-3 gap-1.5 border-t bg-background p-2.5">
            <SendWhatsAppButton sale={sale} />
            <SendEmailButton sale={sale} />
            <Button
              onClick={doPrint}
              disabled={printing}
              size="cashier"
              className="col-span-1"
            >
              {printing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending…
                </>
              ) : (
                <>
                  <Printer className="h-4 w-4" />
                  {printedOnce ? 'Print again' : 'Print'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {canAddCustomer && showCustomerForm && (
        <CustomerFormModal
          onSave={() => {
            setShowCustomerForm(false);
            toast.success('Customer saved');
          }}
          onClose={() => setShowCustomerForm(false)}
        />
      )}
    </>
  );
}

function SendEmailButton({ sale }) {
  const hasEmail = !!sale.customer_email;
  const onClick = () => {
    if (!hasEmail) {
      toast.warning('This customer has no email on file. Add one in Customers.');
      return;
    }
    toast.info('Email receipts are coming once the mail gateway is configured.');
  };
  return (
    <Button variant="outline" size="cashier" onClick={onClick} className="gap-1.5">
      <Mail className="h-4 w-4" />
      Email
    </Button>
  );
}

function SendWhatsAppButton({ sale }) {
  const phone = (sale.customer_phone || sale.customer?.phone || '').replace(/\D/g, '');

  const onClick = () => {
    if (!phone) {
      toast.warning('Add a customer phone number to send via WhatsApp.');
      return;
    }
    const message = buildWhatsAppMessage(sale);
    const url = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <Button variant="outline" size="cashier" onClick={onClick} className="gap-1.5 text-[#128C7E] hover:text-[#128C7E]">
      <WhatsAppIcon className="h-4 w-4" />
      WhatsApp
    </Button>
  );
}
