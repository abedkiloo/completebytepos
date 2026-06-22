import React from 'react';
import { User, UserPlus } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';

/**
 * Shown when the cashier tries partial payment without a registered customer.
 */
export default function PartialPaymentCustomerDialog({
  open,
  onSelectCustomer,
  onAddCustomer,
  onClose,
  canAddCustomer = false,
}) {
  return (
    <Dialog
      open={!!open}
      onOpenChange={(next) => {
        if (!next) onClose?.();
      }}
    >
      <DialogContent className="sm:max-w-md" description="Select a customer before payment on account.">
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
              <User className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <DialogTitle>Select a customer first</DialogTitle>
              <DialogDescription className="text-sm leading-relaxed">
                Partial payments and pay-later sales post the balance to a customer account.
                Search for an existing customer below, or add a new one — then enable payment on
                account again.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:space-x-0">
          <Button type="button" className="w-full" onClick={onSelectCustomer}>
            Search customer
          </Button>
          {canAddCustomer && (
            <Button type="button" variant="outline" className="w-full gap-1.5" onClick={onAddCustomer}>
              <UserPlus className="h-4 w-4" />
              Add new customer
            </Button>
          )}
          <Button type="button" variant="ghost" className="w-full" onClick={onClose}>
            Not now
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
