import React, { useState } from 'react';
import { Plus } from 'lucide-react';

import { salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import NormalSaleModal from './NormalSaleModal';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { PageShell, PageHeader } from '../page';

const NormalSale = () => {
  const [showSaleModal, setShowSaleModal] = useState(false);

  const handleSaveSale = async (saleData) => {
    try {
      const response = await salesAPI.create(saleData);

      if (!response.data.wallet_credit_added && !response.data.wallet_amount_used) {
        if (response.data.invoice) {
          toast.success('Sale completed and invoice created successfully');
        } else {
          toast.success('Sale completed successfully');
        }
      }

      return response;
    } catch (error) {
      toast.error('Failed to create sale: ' + (error.response?.data?.error || error.message));
      throw error;
    }
  };

  return (
    <PageShell narrow>
      <PageHeader
        title="Normal Sale"
        description="Create sales with customer invoicing and payment plans."
      >
        <Button onClick={() => setShowSaleModal(true)}>
          <Plus className="h-4 w-4" />
          Add sales
        </Button>
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Normal sale features</CardTitle>
          <CardDescription>
            Invoiced sales with flexible payment options including partial pay and installments.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <ul className="list-inside list-disc space-y-1">
            <li>Automatic invoice creation</li>
            <li>Customer selection and management</li>
            <li>Partial payments and installments</li>
            <li>Variant selection for products</li>
          </ul>
          <p>
            Click <span className="font-medium text-foreground">Add sales</span> to open the sale
            dialog. Normal sales always create an invoice.
          </p>
        </CardContent>
      </Card>

      {showSaleModal && (
        <NormalSaleModal
          isOpen={showSaleModal}
          onClose={() => setShowSaleModal(false)}
          onSave={handleSaveSale}
        />
      )}
    </PageShell>
  );
};

export default NormalSale;
