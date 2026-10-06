import React, { useEffect, useMemo, useState } from 'react';
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
import { CustomerWalletBalance } from '../../Customers/CustomerWalletBalance';
import { customersAPI } from '../../../services/api';
import { useDebouncedValue } from '../../../hooks/useDebouncedValue';

const WALK_IN = { id: 'walk-in', name: 'Walk-in customer' };

function rowsFromResponse(data) {
  return data?.results || data || [];
}

/**
 * Searchable customer picker for POS. Searches the server so every customer
 * can be found — not only the first page preloaded into memory.
 */
export function CustomerPicker({
  customers = [],
  selectedCustomer,
  onSelect,
  onAddNew,
  requireCustomer = false,
  showCustomerCode = true,
  showWalletBalance = false,
  searchOnServer = true,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, 280);
  const [remoteRows, setRemoteRows] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !searchOnServer) return undefined;
    let cancelled = false;
    setLoading(true);
    customersAPI
      .list({
        is_active: true,
        page_size: 50,
        ...(debouncedQuery.trim() ? { search: debouncedQuery.trim() } : {}),
      })
      .then((res) => {
        if (!cancelled) setRemoteRows(rowsFromResponse(res.data));
      })
      .catch(() => {
        if (!cancelled) setRemoteRows([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, debouncedQuery, searchOnServer]);

  const filtered = useMemo(() => {
    const source = searchOnServer ? remoteRows : customers;
    let base = requireCustomer
      ? source.filter((c) => c.id !== 'walk-in')
      : source;
    if (
      selectedCustomer &&
      selectedCustomer.id !== 'walk-in' &&
      !base.some((c) => String(c.id) === String(selectedCustomer.id))
    ) {
      base = [selectedCustomer, ...base];
    }
    if (!requireCustomer && !searchOnServer) {
      // keep walk-in for local lists that already include it
    }
    if (searchOnServer) return base;
    if (!query) return requireCustomer ? base.filter((c) => c.id !== 'walk-in') : base;
    const q = query.toLowerCase();
    return base.filter(
      (c) =>
        c.name?.toLowerCase().includes(q) ||
        c.owner_name?.toLowerCase().includes(q) ||
        c.contact_person?.toLowerCase().includes(q) ||
        c.phone?.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.customer_code?.toLowerCase().includes(q)
    );
  }, [
    customers,
    remoteRows,
    query,
    requireCustomer,
    searchOnServer,
    selectedCustomer,
  ]);

  const showWalkIn = !requireCustomer;

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setQuery('');
          setOpen(true);
        }}
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
          {showWalletBalance && selectedCustomer?.wallet_balance != null && (
            <div className="text-xs">
              <CustomerWalletBalance
                balance={selectedCustomer.wallet_balance}
                showZero
                className="font-medium"
              />
            </div>
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
              placeholder="Search duka, owner, contact, phone…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="h-10 pl-10"
            />
          </div>

          <ScrollArea className="-mx-2 h-72">
            <ul className="px-2">
              {showWalkIn ? (
                <li key="walk-in">
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(WALK_IN);
                      setOpen(false);
                    }}
                    className={cn(
                      'flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm',
                      selectedCustomer?.id === 'walk-in' || !selectedCustomer
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-accent'
                    )}
                  >
                    <div className="truncate font-medium">{WALK_IN.name}</div>
                  </button>
                </li>
              ) : null}
              {loading ? (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                  Searching customers…
                </li>
              ) : null}
              {!loading &&
                filtered.map((c) => {
                  const active = String(selectedCustomer?.id) === String(c.id);
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
                              c.owner_name ? `Owner: ${c.owner_name}` : null,
                              c.contact_person ? `Contact: ${c.contact_person}` : null,
                              c.phone,
                              c.email,
                              showCustomerCode ? c.customer_code : null,
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </div>
                          {showWalletBalance && c.wallet_balance != null && (
                            <div className="mt-0.5 text-xs">
                              <CustomerWalletBalance balance={c.wallet_balance} showZero />
                            </div>
                          )}
                        </div>
                        {active && <Check className="h-4 w-4 shrink-0" />}
                      </button>
                    </li>
                  );
                })}
              {!loading && filtered.length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">
                  {query.trim()
                    ? `No customers match "${query}".`
                    : 'No customers found.'}
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
