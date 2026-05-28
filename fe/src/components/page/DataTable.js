import React from 'react';
import { cn } from '../../lib/cn';
import { Card } from '../ui/card';

export function DataTable({ children, className }) {
  return (
    <Card className={cn('overflow-hidden shadow-sm', className)}>
      <div className="overflow-x-auto">
        <table className="w-full caption-bottom text-sm">{children}</table>
      </div>
    </Card>
  );
}

export function DataTableHeader({ children }) {
  return (
    <thead className="border-b bg-muted/40 [&_tr]:border-b">
      <tr className="text-left">{children}</tr>
    </thead>
  );
}

export function DataTableHead({ children, className, align = 'left' }) {
  return (
    <th
      className={cn(
        'h-11 px-4 font-medium text-muted-foreground',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className
      )}
    >
      {children}
    </th>
  );
}

export function DataTableBody({ children }) {
  return <tbody className="[&_tr:last-child]:border-0">{children}</tbody>;
}

export function DataTableRow({ children, className, inactive }) {
  return (
    <tr
      className={cn(
        'border-b transition-colors hover:bg-muted/30',
        inactive && 'opacity-60',
        className
      )}
    >
      {children}
    </tr>
  );
}

export function DataTableCell({ children, className, align = 'left' }) {
  return (
    <td
      className={cn(
        'px-4 py-3 align-middle',
        align === 'right' && 'text-right tabular-nums',
        align === 'center' && 'text-center',
        className
      )}
    >
      {children}
    </td>
  );
}
