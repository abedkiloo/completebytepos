import React, { useState } from 'react';
import { Download, FileSpreadsheet, FileText } from 'lucide-react';

import { reportsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { EXPORT_FORMATS, reportExportPath } from '../../utils/reportExport';
import { Button } from '../ui/button';

const ICONS = {
  pdf: FileText,
  xlsx: FileSpreadsheet,
  csv: Download,
};

export default function ReportExportButtons({
  slug,
  params = {},
  disabled = false,
  size = 'sm',
}) {
  const [busy, setBusy] = useState(null);
  if (!reportExportPath(slug)) return null;

  const download = async (format) => {
    setBusy(format);
    try {
      await reportsAPI.exportFile(slug, params, format);
      toast.success(
        format === 'pdf'
          ? 'PDF downloaded'
          : format === 'csv'
            ? 'CSV downloaded'
            : 'Excel downloaded'
      );
    } catch (err) {
      toast.error(err?.message || 'Could not download report');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      {EXPORT_FORMATS.map((fmt) => {
        const Icon = ICONS[fmt.id] || Download;
        return (
          <Button
            key={fmt.id}
            type="button"
            variant={fmt.id === 'pdf' ? 'default' : 'outline'}
            size={size}
            disabled={disabled || Boolean(busy)}
            onClick={() => download(fmt.id)}
            aria-label={`Download ${fmt.label}`}
          >
            <Icon className="h-4 w-4" />
            {busy === fmt.id ? 'Downloading…' : fmt.label}
          </Button>
        );
      })}
    </div>
  );
}
