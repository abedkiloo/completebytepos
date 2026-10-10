import React from 'react';
import { Loader2 } from 'lucide-react';

import TypicalGoodsFields from './TypicalGoodsFields';
import KenyaLocationFields from './KenyaLocationFields';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { cn } from '../../lib/cn';

export default function CustomerFormDialog({
  open,
  onOpenChange,
  editing,
  formData,
  formErrors,
  onChange,
  onSubmit,
  saving,
  showCustomerType = true,
  showTaxId = true,
  showNotes = true,
  showStatus = true,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'left-[50%] top-[4vh] flex w-[calc(100%-2rem)] max-h-[92dvh] translate-x-[-50%] translate-y-0',
          'flex-col gap-0 overflow-hidden p-0 sm:max-w-2xl'
        )}
        description={
          editing
            ? 'Update this duka’s owner, landmark, and the goods they buy most.'
            : 'Register a duka to track sales, wallet balance, and credit.'
        }
      >
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4 pr-12">
          <DialogTitle>{editing ? 'Edit duka' : 'Register duka'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={onSubmit} className="flex flex-col">
          <div
            className="dialog-form-scroll max-h-[calc(92dvh-10.5rem)] overflow-y-auto overscroll-contain px-6 py-4"
            role="region"
            aria-label="Duka details"
          >
            <div className="flex flex-col gap-4 pb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Basics
              </p>
              <Field label="Duka name" htmlFor="cust-name" required error={formErrors.name}>
                <Input
                  id="cust-name"
                  value={formData.name}
                  onChange={(e) => onChange('name', e.target.value)}
                  placeholder="e.g. Wambua Hardware"
                  autoFocus
                />
              </Field>

              <Field label="Owner's name" htmlFor="cust-owner">
                <Input
                  id="cust-owner"
                  value={formData.owner_name}
                  onChange={(e) => onChange('owner_name', e.target.value)}
                  placeholder="e.g. Jane Wambua"
                />
              </Field>

              <Field label="Phone" htmlFor="cust-phone" error={formErrors.phone}>
                <Input
                  id="cust-phone"
                  type="tel"
                  inputMode="tel"
                  value={formData.phone}
                  onChange={(e) => onChange('phone', e.target.value)}
                  placeholder="0712 345 678"
                />
              </Field>

              {showCustomerType && (
                <Field label="Type" htmlFor="cust-type">
                  <SegmentedControl
                    value={formData.customer_type}
                    onChange={(v) => onChange('customer_type', v)}
                    options={[
                      { value: 'individual', label: 'Individual' },
                      { value: 'business', label: 'Business' },
                    ]}
                  />
                </Field>
              )}

              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Other details <span className="font-normal normal-case">(optional)</span>
              </p>
              <Field label="Email" htmlFor="cust-email" error={formErrors.email}>
                <Input
                  id="cust-email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => onChange('email', e.target.value)}
                  placeholder="name@example.com"
                />
              </Field>

              <KenyaLocationFields
                formData={formData}
                formErrors={formErrors}
                onChange={onChange}
              />

              {showTaxId && (
                <Field
                  label="Tax ID / VAT number"
                  htmlFor="cust-tax"
                  hint="Leave blank if not applicable."
                >
                  <Input
                    id="cust-tax"
                    value={formData.tax_id}
                    onChange={(e) => onChange('tax_id', e.target.value)}
                  />
                </Field>
              )}

              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Notes
              </p>
              <Field label="Landmark" htmlFor="cust-address">
                <textarea
                  id="cust-address"
                  value={formData.address}
                  onChange={(e) => onChange('address', e.target.value)}
                  rows={2}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="Next to the market, opposite the bus stage…"
                />
              </Field>

              <Field label="Contact person" htmlFor="cust-contact">
                <Input
                  id="cust-contact"
                  value={formData.contact_person}
                  onChange={(e) => onChange('contact_person', e.target.value)}
                  placeholder="Who to ask for, if not the owner"
                />
              </Field>

              {showNotes && (
                <Field label="Internal notes" htmlFor="cust-notes">
                  <textarea
                    id="cust-notes"
                    value={formData.notes}
                    onChange={(e) => onChange('notes', e.target.value)}
                    rows={3}
                    className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    placeholder="Credit terms, delivery instructions…"
                  />
                </Field>
              )}

              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Goods they buy most <span className="font-normal normal-case">(optional)</span>
              </p>
              <TypicalGoodsFields
                value={formData.typical_goods}
                onChange={(goods) => onChange('typical_goods', goods)}
              />

              {showStatus && (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => onChange('is_active', e.target.checked)}
                    className="h-4 w-4 rounded border-input text-primary focus:ring-1 focus:ring-ring"
                  />
                  <span>Active — appears in duka pickers</span>
                </label>
              )}
            </div>
          </div>

          <DialogFooter className="shrink-0 gap-2 border-t bg-background px-6 py-4 sm:gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : editing ? (
                'Save changes'
              ) : (
                'Register duka'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, htmlFor, required = false, error, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor} className="flex items-center gap-1">
        <span>{label}</span>
        {required && <span className="text-destructive">*</span>}
      </Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function SegmentedControl({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-md border bg-background">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'h-10 px-4 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md',
            value === opt.value
              ? 'bg-primary text-primary-foreground'
              : 'text-foreground hover:bg-accent'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
