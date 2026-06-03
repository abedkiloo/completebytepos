import React from 'react';
import { fieldError } from '../../utils/formValidation';

/**
 * Wraps a label + control + inline error message with consistent invalid styling.
 */
const FormField = ({
  label,
  htmlFor,
  required = false,
  errors = {},
  name,
  hint,
  className = '',
  children,
}) => {
  const message = name ? fieldError(errors, name) : undefined;

  return (
    <div
      className={[
        'form-group',
        message ? 'has-error field-error' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {label ? (
        <label htmlFor={htmlFor || name}>
          {label}
          {required ? ' *' : ''}
        </label>
      ) : null}
      {children}
      {message ? (
        <span className="field-error-message" role="alert">
          {message}
        </span>
      ) : null}
      {!message && hint ? (
        <small className="form-text text-muted">{hint}</small>
      ) : null}
    </div>
  );
};

export default FormField;
