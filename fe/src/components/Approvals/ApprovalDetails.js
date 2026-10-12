import React, { useState } from 'react';
import { NotebookText } from 'lucide-react';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

/** Qty for display — coerces scientific notation like ``1E+1`` to ``10``. */
export function formatApprovalQty(value) {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  if (Number.isInteger(n)) return String(n);
  const text = String(n);
  return text.includes('e') || text.includes('E')
    ? n.toFixed(6).replace(/\.?0+$/, '')
    : text;
}

function formatFact(fact) {
  if (fact.kind === 'money') return formatCurrency(Number(fact.value) || 0);
  if (fact.kind === 'datetime') return formatDateTime(fact.value);
  return fact.value;
}

function NotesFactValue({ value, onOpen }) {
  const text = String(value || '').trim();
  if (!text) return '—';
  return (
    <button
      type="button"
      onClick={onOpen}
      className="info-chunk flex max-w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:border-primary/40"
      title="View full notes"
    >
      <NotebookText className="h-4 w-4 shrink-0 text-primary" aria-hidden />
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-primary">{text}</span>
        <span className="block text-[11px] font-medium text-muted-foreground">
          Click to view full notes
        </span>
      </span>
    </button>
  );
}

function FactsGrid({ facts, onOpenNotes }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
      {facts.map((fact) => (
        <div
          key={fact.label}
          className={`flex min-w-0 justify-between gap-3 border-b border-border/40 py-1 ${
            fact.kind === 'notes' ? 'sm:col-span-2' : ''
          }`}
        >
          <dt className="shrink-0 text-muted-foreground">{fact.label}</dt>
          <dd className="min-w-0 break-words text-right font-medium">
            {fact.kind === 'notes' ? (
              <NotesFactValue
                value={fact.value}
                onOpen={() => onOpenNotes?.(String(fact.value || '').trim())}
              />
            ) : (
              formatFact(fact)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function LinesTable({ lines }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Item</th>
            <th className="px-3 py-2 text-right font-medium">Qty</th>
            <th className="px-3 py-2 text-right font-medium">Unit price</th>
            <th className="px-3 py-2 text-right font-medium">Line total</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => (
            <tr key={`${line.name}-${index}`} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2">
                <span className="font-medium">{line.name}</span>
                {line.variant ? (
                  <span className="block text-xs text-muted-foreground">{line.variant}</span>
                ) : null}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{formatApprovalQty(line.quantity)}</td>
              <td className="px-3 py-2 text-right">{formatCurrency(Number(line.unit_price) || 0)}</td>
              <td className="px-3 py-2 text-right font-medium">
                {formatCurrency(Number(line.subtotal) || 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Everything about an approval (sale items, money, customer, collection) before the checker acts. */
export default function ApprovalDetails({ details, className = '' }) {
  const [notesText, setNotesText] = useState(null);
  const sections = Array.isArray(details?.sections) ? details.sections : [];
  if (!sections.length) return null;
  return (
    <>
      <div className={`space-y-4 rounded-md border bg-muted/20 p-3 ${className}`} data-testid="approval-details">
        {sections.map((section) => (
          <section key={section.title} className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {section.title}
            </h4>
            {Array.isArray(section.facts) && section.facts.length ? (
              <FactsGrid facts={section.facts} onOpenNotes={setNotesText} />
            ) : null}
            {Array.isArray(section.lines) && section.lines.length ? (
              <LinesTable lines={section.lines} />
            ) : null}
          </section>
        ))}
      </div>

      <Dialog
        open={notesText != null}
        onOpenChange={(open) => {
          if (!open) setNotesText(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Notes</DialogTitle>
            <DialogDescription>Full notes for this record.</DialogDescription>
          </DialogHeader>
          <div className="reminder-banner max-h-[50vh] overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">
            {notesText || 'No notes.'}
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setNotesText(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
