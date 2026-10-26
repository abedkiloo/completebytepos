import React, { useState } from 'react';
import { customersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import CommitConfirm from '../Shared/CommitConfirm';
import { customerCommitRows } from '../../utils/formCommitSummary';
import {
  CUSTOMER_GENDER_OPTIONS,
  EMPTY_CUSTOMER_FORM,
  customerSavePayload,
  validateCustomerForm,
} from '../../utils/customerFormState';
import { applyCustomerFormFieldUpdate } from '../../utils/customerFormFieldUpdate';
import TypicalGoodsFields from './TypicalGoodsFields';
import KenyaLocationFields from './KenyaLocationFields';
import FormBanner from '../form/FormBanner';
import { formBannerMessage, reportFormError } from '../../utils/formFeedback';

const CustomerFormModal = ({ isOpen, onClose, onCustomerCreated }) => {
  const [formData, setFormData] = useState({ ...EMPTY_CUSTOMER_FORM });
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [showCommitConfirm, setShowCommitConfirm] = useState(false);

  const updateField = (keyOrPatch, value) => {
    setFormData((prev) => applyCustomerFormFieldUpdate(prev, keyOrPatch, value));
    if (typeof keyOrPatch === 'object' && keyOrPatch !== null) {
      const cleared = Object.keys(keyOrPatch).filter((k) => formErrors[k]);
      if (cleared.length) {
        setFormErrors((prev) => {
          const next = { ...prev };
          cleared.forEach((k) => {
            delete next[k];
          });
          return next;
        });
      }
      return;
    }
    if (formErrors[keyOrPatch]) {
      setFormErrors((prev) => {
        const next = { ...prev };
        delete next[keyOrPatch];
        return next;
      });
    }
  };

  const handleClose = () => {
    // Reset form when closing
    setFormData({ ...EMPTY_CUSTOMER_FORM });
    setFormErrors({});
    setShowCommitConfirm(false);
    onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Clear previous errors
    setFormErrors({});
    
    const errors = validateCustomerForm(formData, { requireGender: true });
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      reportFormError(null, Object.values(errors)[0], 5000);
      return;
    }

    setShowCommitConfirm(true);
  };

  const confirmCommit = async () => {
    if (loading) return;
    setLoading(true);
    
    const cleanData = customerSavePayload(formData);
    
    try {
      const response = await customersAPI.create(cleanData);
      const newCustomer = response.data;
      toast.success('Duka registered');
      handleClose();
      
      // Call callback with the new customer
      if (onCustomerCreated) {
        onCustomerCreated(newCustomer);
      }
    } catch (error) {
      // Handle validation errors from backend
      const backendErrors = {};
      let errorMessage = 'Failed to create customer';
      
      if (error.response?.data) {
        const errorData = error.response.data;
        
        // Handle field-level validation errors (DRF format)
        if (typeof errorData === 'object' && !errorData.error) {
          for (const [field, messages] of Object.entries(errorData)) {
            if (Array.isArray(messages)) {
              backendErrors[field] = messages.join(', ');
            } else if (typeof messages === 'string') {
              backendErrors[field] = messages;
            } else {
              backendErrors[field] = JSON.stringify(messages);
            }
          }
          if (Object.keys(backendErrors).length > 0) {
            setFormErrors(backendErrors);
            errorMessage = Object.values(backendErrors)[0];
            reportFormError(null, errorMessage, 8000);
            setLoading(false);
            return; // Don't close modal on validation error
          }
        } else if (errorData.error) {
          errorMessage = errorData.error;
        } else if (typeof errorData === 'string') {
          errorMessage = errorData;
        } else if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      setFormErrors({ _form: errorMessage });
      reportFormError(null, errorMessage, 8000);
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="slide-in-overlay" onClick={handleClose}>
      <div className="slide-in-panel flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>Register duka</h2>
          <button onClick={handleClose} className="slide-in-panel-close">×</button>
        </div>
        
        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit}>
            <FormBanner message={formBannerMessage(formErrors)} />
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Basics
            </p>
            <div className="form-group">
              <label>Duka name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => {
                  setFormData({ ...formData, name: e.target.value });
                  if (formErrors.name) setFormErrors({ ...formErrors, name: '' });
                }}
                className={formErrors.name ? 'error' : ''}
                placeholder="e.g. Wambua Hardware"
                required
                autoFocus
              />
              {formErrors.name && <span className="error-text">{formErrors.name}</span>}
            </div>
            <div className="form-group">
              <label>Owner&apos;s name</label>
              <input
                type="text"
                value={formData.owner_name}
                onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                placeholder="e.g. Jane Wambua"
              />
            </div>
            <div className="form-group">
              <label>Gender *</label>
              <div className="inline-flex rounded-md border bg-background">
                {CUSTOMER_GENDER_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => updateField('gender', opt.value)}
                    className={`h-10 px-4 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md ${
                      formData.gender === opt.value
                        ? 'bg-primary text-primary-foreground'
                        : 'text-foreground hover:bg-accent'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {formErrors.gender && <span className="error-text">{formErrors.gender}</span>}
            </div>
            <div className="form-group">
              <label>Phone</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => {
                  setFormData({ ...formData, phone: e.target.value });
                  if (formErrors.phone) setFormErrors({ ...formErrors, phone: '' });
                }}
                className={formErrors.phone ? 'error' : ''}
                placeholder="0712 345 678"
              />
              {formErrors.phone && <span className="error-text">{formErrors.phone}</span>}
            </div>
            <p className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Other details
              <span className="ml-1 font-normal normal-case">(optional)</span>
            </p>
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => {
                  setFormData({ ...formData, email: e.target.value });
                  if (formErrors.email) setFormErrors({ ...formErrors, email: '' });
                }}
                className={formErrors.email ? 'error' : ''}
              />
              {formErrors.email && <span className="error-text">{formErrors.email}</span>}
            </div>
            <KenyaLocationFields
              formData={formData}
              formErrors={formErrors}
              onChange={updateField}
            />

            <p className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Notes
            </p>
            <div className="form-group">
              <label>Contact person</label>
              <input
                type="text"
                value={formData.contact_person}
                onChange={(e) => setFormData({ ...formData, contact_person: e.target.value })}
                placeholder="Who to ask for, if not the owner"
              />
            </div>

            <p className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Goods they buy most
              <span className="ml-1 font-normal normal-case">(optional)</span>
            </p>
            <TypicalGoodsFields
              value={formData.typical_goods}
              onChange={(typical_goods) => setFormData({ ...formData, typical_goods })}
            />
          </form>
        </div>
        
        <div className="slide-in-panel-footer">
          <button 
            type="button" 
            onClick={handleClose} 
            className="btn btn-secondary"
            disabled={loading}
          >
            Cancel
          </button>
          <button 
            type="button" 
            onClick={handleSubmit} 
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Saving…' : 'Register duka'}
          </button>
        </div>
      </div>
      <CommitConfirm
        open={showCommitConfirm}
        onOpenChange={(open) => {
          if (!open && !loading) setShowCommitConfirm(false);
        }}
        title="Register this duka?"
        description="Review the duka details, then confirm to save."
        rows={customerCommitRows(formData)}
        submitting={loading}
        confirmText="Confirm & register"
        onConfirm={confirmCommit}
      />
    </div>
  );
};

export default CustomerFormModal;
