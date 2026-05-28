import React, { useEffect, useState, useRef } from 'react';
import { Printer, Mail, MessageSquare, Check, Loader2, Receipt as ReceiptIcon } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { toast } from '../../../utils/toast';

import { ThermalReceipt } from './ThermalReceipt';
import { printThermalReceipt } from './printReceipt';
import { useStoreInfo } from './useStoreInfo';
import './ThermalReceipt.css';

/**
 * Wraps the thermal receipt in a Dialog with the actions cashiers actually
 * need: Print (works now), Email and SMS (placeholders until the SMS / email
 * gateway is wired in — see the README in this folder).
 *
 * Opens the receipt preview first. Set ``autoPrint={true}`` (default) to send
 * straight to the printer once per sale; use ``false`` after checkout so the
 * cashier reviews then taps **Print**.
 */
export default function ReceiptDialog({
  sale,
  open,
  onOpenChange,
  autoPrint = true,
}) {
  const store = useStoreInfo(sale);
  const [printing, setPrinting] = useState(false);
  const [printedOnce, setPrintedOnce] = useState(false);
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

  // Fire the auto-print exactly once per sale. Re-opening the dialog for the
  // same sale should NOT trigger another print — the cashier may just be
  // looking at the receipt.
  useEffect(() => {
    if (!open || !autoPrint || !sale?.id) return;
    if (autoPrintFiredFor.current === sale.id) return;
    autoPrintFiredFor.current = sale.id;
    doPrint();
    // doPrint is stable enough — and we explicitly only want this to react
    // to open / sale.id changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, autoPrint, sale?.id]);

  if (!sale) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md gap-0 p-0"
        description={`Receipt for sale ${sale.sale_number}. Print, email, or send by SMS.`}
      >
        <DialogHeader className="border-b px-5 py-3">
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

        <ScrollArea className="max-h-[60vh] bg-muted/30 px-4 py-5">
          <div className="mx-auto w-fit rounded-md bg-white shadow-sm ring-1 ring-border print:shadow-none print:ring-0">
            <ThermalReceipt sale={sale} store={store} />
          </div>
        </ScrollArea>

        <DialogFooter className="grid grid-cols-2 gap-2 border-t bg-background p-3 sm:flex sm:flex-row-reverse sm:justify-between">
          <div className="col-span-2 flex gap-2 sm:contents">
            <Button
              onClick={doPrint}
              disabled={printing}
              size="cashier"
              className="flex-1 sm:flex-initial"
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
            <SendEmailButton sale={sale} />
            <SendSmsButton sale={sale} />
          </div>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            size="cashier"
            className="col-span-2 sm:col-auto"
          >
            Done · new sale
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Placeholder buttons for email / SMS receipts.
 *
 * The frontend wiring is here so the next change is purely backend: add the
 * /sales/<id>/email_receipt and /sales/<id>/sms_receipt endpoints and remove
 * the early-return below. Until then we tell the cashier honestly rather
 * than pretending it worked.
 */
function SendEmailButton({ sale }) {
  const hasEmail = !!sale.customer_email;
  const onClick = () => {
    if (!hasEmail) {
      toast.warning("This customer has no email on file. Add one in Customers.");
      return;
    }
    toast.info('Email receipts are coming once the mail gateway is configured.');
  };
  return (
    <Button variant="outline" size="cashier" onClick={onClick} className="flex-1 sm:flex-initial">
      <Mail className="h-4 w-4" />
      Email
    </Button>
  );
}

function SendSmsButton({ sale }) {
  const hasPhone = !!sale.customer_phone;
  const onClick = () => {
    if (!hasPhone) {
      toast.warning("This customer has no phone on file. Add one in Customers.");
      return;
    }
    toast.info('SMS receipts are coming once the SMS provider is configured.');
  };
  return (
    <Button variant="outline" size="cashier" onClick={onClick} className="flex-1 sm:flex-initial">
      <MessageSquare className="h-4 w-4" />
      SMS
    </Button>
  );
}
