import React, { useState, useMemo } from 'react';
import { User as UserIcon, Plus, Search, Check } from 'lucide-react';

import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { cn } from '../../../lib/cn';

/**
 * Single field that always shows the current customer name and opens a
 * searchable picker on click. Replaces the old SearchableSelect on the POS
 * screen because cashiers shouldn't have to dig through a tall dropdown to
 * switch from Walk-in to a registered customer.
 */
export function CustomerPicker({
  customers = [],
  selectedCustomer,
  onSelect,
  onAddNew,
  requireCustomer = false,
  showCustomerCode = true,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const base = requireCustomer
      ? customers.filter((c) => c.id !== 'walk-in')
      : customers;
    if (!query) return base;
    const q = query.toLowerCase();
    return base.filter(
      (c) =>
        c.name?.toLowerCase().includes(q) ||
        c.phone?.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.customer_code?.toLowerCase().includes(q)
    );
  }, [customers, query, requireCustomer]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="pos-target flex w-full items-center gap-2 rounded-md border bg-background px-3 py-2 text-left text-sm hover:bg-accent"
      >
        <UserIcon className="h-4 w-4 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium text-foreground">
            {selectedCustomer?.name || (requireCustomer ? 'Select customer' : 'Walk-in customer')}
          </div>
          {selectedCustomer?.phone && (
            <div className="truncate text-xs text-muted-foreground">{selectedCustomer.phone}</div>
          )}
        </div>
        <span className="text-xs font-medium text-primary">Change</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="max-w-md"
          description="Search for and pick an existing customer to attach to this sale, or clear to checkout as a walk-in."
        >
          <DialogHeader>
            <DialogTitle>Select customer</DialogTitle>
          </DialogHeader>

          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              placeholder="Search name, phone, email, or code…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-10 pl-10"
            />
          </div>

          <ScrollArea className="-mx-2 h-72">
            <ul className="px-2">
              {filtered.map((c) => {
                const active = selectedCustomer?.id === c.id;
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(c);
                        setOpen(false);
                      }}
                      className={cn(
                        'flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm',
                        active ? 'bg-primary/10 text-primary' : 'hover:bg-accent'
                      )}
                    >
                      <div className="min-w-0">
                        <div className="truncate font-medium">{c.name}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {[
                            c.phone,
                            c.email,
                            showCustomerCode ? c.customer_code : null,
                          ]
                            .filter(Boolean)
                            .join(' · ')}
                        </div>
                      </div>
                      {active && <Check className="h-4 w-4 shrink-0" />}
                    </button>
                  </li>
                );
              })}
              {filtered.length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                  No customers match "{query}".
                </li>
              )}
            </ul>
          </ScrollArea>

          {onAddNew && (
            <Button variant="outline" onClick={() => { setOpen(false); onAddNew(); }}>
              <Plus className="h-4 w-4" />
              Add new customer
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
