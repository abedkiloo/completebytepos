import React, { useState } from 'react';
import { salesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import Layout from '../Layout/Layout';
import NormalSaleModal from './NormalSaleModal';
import '../../styles/shared.css';
import './NormalSale.css';

const NormalSale = () => {
  const [showSaleModal, setShowSaleModal] = useState(false);

  const handleSaveSale = async (saleData) => {
    try {
      const response = await salesAPI.create(saleData);
      
      // Don't show generic success here - let modal handle wallet messages
      // Only show if no wallet message will be shown
      if (!response.data.wallet_credit_added && !response.data.wallet_amount_used) {
        if (response.data.invoice) {
          toast.success('Sale completed and invoice created successfully');
        } else {
          toast.success('Sale completed successfully');
        }
      }
      
      // Return response so modal can access wallet information
      return response;
    } catch (error) {
      toast.error('Failed to create sale: ' + (error.response?.data?.error || error.message));
      throw error; // Re-throw to let modal handle it
    }
  };

  return (
    <Layout>
      <div className="normal-sale-page">
        <div className="page-header">
          <div>
            <h1>Normal Sale</h1>
            <p>Create sales with customer invoicing and payment plans</p>
          </div>
          <div>
              <button 
              className="btn btn-primary"
              onClick={() => setShowSaleModal(true)}
              >
              <span>+</span>
              <span>Add Sales</span>
              </button>
          </div>
        </div>

        <div className="normal-sale-content">
          <div className="normal-sale-info-card">
            <h3>Normal Sale Features</h3>
            <ul>
              <li>✓ Automatic invoice creation</li>
              <li>✓ Customer selection and management</li>
              <li>✓ Support for partial payments</li>
              <li>✓ Payment plans and installments</li>
              <li>✓ Payment reminders</li>
              <li>✓ Variant selection for products</li>
            </ul>
            <p className="normal-sale-info-text">
              Click "Add Sales" to create a new sale with invoice. Normal sales always create an invoice
              and support flexible payment options including installments.
            </p>
          </div>
        </div>

        {showSaleModal && (
          <NormalSaleModal
            isOpen={showSaleModal}
            onClose={() => setShowSaleModal(false)}
            onSave={handleSaveSale}
          />
        )}
      </div>
    </Layout>
  );
};

export default NormalSale;
