import React from 'react';
import { buildApprovalDiffRows } from '../../utils/approvalDisplay';

export default function ApprovalChangeTable({ originalValues, proposedValues }) {
  const rows = buildApprovalDiffRows(originalValues, proposedValues);

  if (!rows.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No field-level details were recorded for this request.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">What changes</th>
            <th className="px-3 py-2 font-medium">Currently approved</th>
            <th className="px-3 py-2 font-medium">Requested</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 font-medium">{row.label}</td>
              <td className="px-3 py-2 text-muted-foreground">{row.before}</td>
              <td className="px-3 py-2">{row.after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
