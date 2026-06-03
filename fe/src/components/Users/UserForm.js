import React, { useState, useEffect, useCallback } from 'react';
import { usersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import SearchableSelect from '../Shared/SearchableSelect';
import FormField from '../form/FormField';
import {
  normalizeApiErrors,
  hasValidationErrors,
  firstErrorField,
} from '../../utils/formValidation';
import { buildUserPayload, validateUserForm } from '../../utils/userFormPayload';

const UserForm = ({
  user,
  roles,
  onClose,
  onSave,
  hideStatusToggles = false,
  showEmail = true,
  showFullName = true,
  showPhone = true,
  showStaffFlag = true,
  showInlineRoles = true,
}) => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_staff: false,
    is_active: true,
    role: 'cashier',
    custom_role_id: null,
    phone_number: '',
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitAttempted, setSubmitAttempted] = useState(false);

  const formOptions = {
    isEdit: !!user,
    showEmail,
    showFullName,
    showPhone,
    showStaffFlag,
    hideStatusToggles,
    showInlineRoles,
  };

  useEffect(() => {
    if (user) {
      setFormData({
        username: user.username || '',
        email: user.email || '',
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        password: '',
        is_staff: user.is_staff || false,
        is_active: user.is_active !== undefined ? user.is_active : true,
        role: user.profile?.role || 'cashier',
        custom_role_id: user.profile?.custom_role?.id || null,
        phone_number: user.profile?.phone_number || '',
      });
    }
    setErrors({});
    setSubmitAttempted(false);
  }, [user]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        delete next._form;
        return next;
      });
    }
  };

  const scrollToFirstError = useCallback((fieldErrors) => {
    const field = firstErrorField(fieldErrors);
    if (!field) return;
    const el = document.getElementById(field) || document.querySelector(`[name="${field}"]`);
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    el?.focus?.();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitAttempted(true);

    const clientErrors = validateUserForm(formData, formOptions);
    if (hasValidationErrors(clientErrors)) {
      setErrors(clientErrors);
      scrollToFirstError(clientErrors);
      return;
    }

    setLoading(true);
    setErrors({});

    try {
      const payload = buildUserPayload(formData, formOptions);

      if (user) {
        await usersAPI.update(user.id, payload);
        toast.success('User updated successfully');
      } else {
        await usersAPI.create(payload);
        toast.success('User created successfully');
      }

      if (onSave) onSave();
      onClose();
    } catch (error) {
      if (error.response?.data) {
        const apiErrors = normalizeApiErrors(error.response.data);
        setErrors(apiErrors);
        scrollToFirstError(apiErrors);
        if (apiErrors._form && !firstErrorField(apiErrors)) {
          toast.error(apiErrors._form);
        }
      } else {
        toast.error('Failed to save user. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const formInvalid =
    submitAttempted && hasValidationErrors(validateUserForm(formData, formOptions));

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(ev) => ev.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{user ? 'Edit User' : 'Create New User'}</h2>
          <button type="button" className="slide-in-panel-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="slide-in-panel-body">
          <form onSubmit={handleSubmit} className="user-form" noValidate>
            {errors._form && (
              <div className="form-banner-error" role="alert">
                {errors._form}
              </div>
            )}

            {formInvalid && (
              <div className="form-banner-error" role="status">
                Please fix the highlighted fields before saving.
              </div>
            )}

            <div className="form-row">
              <FormField
                label="Username"
                name="username"
                htmlFor="username"
                required
                errors={errors}
              >
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  disabled={!!user}
                  aria-invalid={Boolean(errors.username)}
                />
              </FormField>

              {showEmail ? (
                <FormField label="Email" name="email" htmlFor="email" errors={errors}>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    aria-invalid={Boolean(errors.email)}
                  />
                </FormField>
              ) : null}
            </div>

            {showFullName ? (
              <div className="form-row">
                <FormField
                  label="First Name"
                  name="first_name"
                  htmlFor="first_name"
                  errors={errors}
                >
                  <input
                    type="text"
                    id="first_name"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleChange}
                    aria-invalid={Boolean(errors.first_name)}
                  />
                </FormField>

                <FormField
                  label="Last Name"
                  name="last_name"
                  htmlFor="last_name"
                  errors={errors}
                >
                  <input
                    type="text"
                    id="last_name"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleChange}
                    aria-invalid={Boolean(errors.last_name)}
                  />
                </FormField>
              </div>
            ) : null}

            {!user && (
              <FormField
                label="Password"
                name="password"
                htmlFor="password"
                required
                errors={errors}
              >
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  minLength={6}
                  aria-invalid={Boolean(errors.password)}
                />
              </FormField>
            )}

            {showInlineRoles ? (
              <div className="form-row">
                <FormField label="Default Role" name="role" errors={errors}>
                  <SearchableSelect
                    name="role"
                    value={formData.role}
                    onChange={handleChange}
                    invalid={Boolean(errors.role)}
                    options={[
                      { id: 'cashier', name: 'Cashier' },
                      { id: 'manager', name: 'Manager' },
                      { id: 'admin', name: 'Admin' },
                      { id: 'super_admin', name: 'Super Admin' },
                    ]}
                    placeholder="Select default role"
                  />
                </FormField>

                <FormField label="Custom Role" name="custom_role_id" errors={errors}>
                  <SearchableSelect
                    name="custom_role_id"
                    value={formData.custom_role_id || ''}
                    onChange={handleChange}
                    invalid={Boolean(errors.custom_role_id)}
                    options={[
                      { id: '', name: 'None' },
                      ...roles.map((role) => ({ id: role.id, name: role.name })),
                    ]}
                    placeholder="None"
                  />
                </FormField>
              </div>
            ) : null}

            {showPhone ? (
              <FormField label="Phone Number" name="phone_number" htmlFor="phone_number" errors={errors}>
                <input
                  type="text"
                  id="phone_number"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleChange}
                  aria-invalid={Boolean(errors.phone_number)}
                />
              </FormField>
            ) : null}

            <div className="form-row">
              {showStaffFlag ? (
                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      name="is_staff"
                      checked={formData.is_staff}
                      onChange={handleChange}
                    />
                    Staff Member
                  </label>
                </div>
              ) : null}

              {!hideStatusToggles && (
                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      name="is_active"
                      checked={formData.is_active}
                      onChange={handleChange}
                    />
                    Active
                  </label>
                </div>
              )}
            </div>
          </form>
        </div>

        <div className="slide-in-panel-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            className="btn btn-primary"
            disabled={loading}
          >
            {loading ? 'Saving...' : user ? 'Update' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UserForm;
