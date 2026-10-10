import { typicalGoodsPayload } from '../components/Customers/TypicalGoodsFields';
import { emailMessage, personNameMessage, phoneMessage } from './formValidation';

export const KENYA_LOCATION_DEFAULTS = {
  county: 'Nairobi',
  sub_county: 'Starehe',
  ward: 'Landimawe',
};

export const EMPTY_CUSTOMER_FORM = {
  name: '',
  owner_name: '',
  customer_type: 'business',
  email: '',
  phone: '',
  address: '',
  city: KENYA_LOCATION_DEFAULTS.county,
  county: KENYA_LOCATION_DEFAULTS.county,
  sub_county: KENYA_LOCATION_DEFAULTS.sub_county,
  ward: KENYA_LOCATION_DEFAULTS.ward,
  country: 'Kenya',
  tax_id: '',
  notes: '',
  contact_person: '',
  typical_goods: [''],
  is_active: true,
};

export function customerFormFromRecord(customer) {
  if (!customer) return { ...EMPTY_CUSTOMER_FORM };
  return {
    name: customer.name || '',
    owner_name: customer.owner_name || '',
    customer_type: customer.customer_type || 'business',
    email: customer.email || '',
    phone: customer.phone || '',
    address: customer.address || '',
    city: customer.city || customer.county || '',
    county: customer.county || customer.city || KENYA_LOCATION_DEFAULTS.county,
    sub_county: customer.sub_county || KENYA_LOCATION_DEFAULTS.sub_county,
    ward: customer.ward || KENYA_LOCATION_DEFAULTS.ward,
    country: customer.country || 'Kenya',
    tax_id: customer.tax_id || '',
    notes: customer.notes || '',
    contact_person: customer.contact_person || '',
    typical_goods:
      Array.isArray(customer.typical_goods) && customer.typical_goods.length
        ? customer.typical_goods
        : [''],
    is_active: customer.is_active !== undefined ? customer.is_active : true,
  };
}

export function customerSavePayload(formData) {
  return {
    name: String(formData.name || '').trim(),
    customer_type: formData.customer_type,
    email: String(formData.email || '').trim(),
    phone: String(formData.phone || '').trim(),
    owner_name: String(formData.owner_name || '').trim(),
    address: String(formData.address || '').trim(),
    city: String(formData.county || formData.city || '').trim(),
    county: String(formData.county || '').trim(),
    sub_county: String(formData.sub_county || '').trim(),
    ward: String(formData.ward || '').trim(),
    country: String(formData.country || '').trim() || 'Kenya',
    tax_id: String(formData.tax_id || '').trim(),
    notes: String(formData.notes || '').trim(),
    contact_person: String(formData.contact_person || '').trim(),
    typical_goods: typicalGoodsPayload(formData.typical_goods),
    is_active: formData.is_active,
  };
}

export function validateCustomerForm(formData) {
  const errors = {};
  const nameErr = personNameMessage(formData.name, {
    label: 'duka name',
    example: 'Wambua Hardware',
  });
  if (nameErr) errors.name = nameErr;

  const emailErr = emailMessage(formData.email);
  if (emailErr) errors.email = emailErr;

  const phoneErr = phoneMessage(formData.phone);
  if (phoneErr) errors.phone = phoneErr;

  return errors;
}

export function customerFormBackendErrors(data) {
  if (!data || typeof data !== 'object' || data.error || data.detail) return null;
  const backendErrors = {};
  for (const [field, messages] of Object.entries(data)) {
    backendErrors[field] = Array.isArray(messages) ? messages.join(', ') : String(messages);
  }
  return Object.keys(backendErrors).length ? backendErrors : null;
}
