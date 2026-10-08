import React, { useEffect, useState } from 'react';

import { messagingAPI } from '../../services/api';
import CustomerSmsBlastDialog from './CustomerSmsBlastDialog';

/**
 * Back-compat wrapper: Customer Week send via the shared blast dialog.
 */
export default function CustomerWeekPromoDialog({ open, onOpenChange }) {
  const [templates, setTemplates] = useState([]);

  useEffect(() => {
    if (!open) return;
    messagingAPI
      .listTemplates()
      .then((res) => setTemplates(res.data?.results || []))
      .catch(() => setTemplates([]));
  }, [open]);

  return (
    <CustomerSmsBlastDialog
      open={open}
      onOpenChange={onOpenChange}
      templates={templates}
      initialTemplateKey="promo_customer_week"
    />
  );
}
