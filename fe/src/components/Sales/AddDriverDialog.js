import React, { useState } from 'react';
import { dispatchAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { required } from '../../utils/formValidation';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export function splitDriverDisplayName(value) {
  const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return { firstName: '', lastName: '' };
  if (parts.length === 1) return { firstName: parts[0], lastName: '' };
  return { firstName: parts[0], lastName: parts.slice(1).join(' ') };
}

export function createDriverPayload({ displayName, phone }) {
  return {
    display_name: String(displayName || '').trim(),
    phone: String(phone || '').trim(),
  };
}

export default function AddDriverDialog({ open, onClose, onCreated }) {
  const [displayName, setDisplayName] = useState('');
  const [phone, setPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState(null);

  if (!open) return null;

  const reset = () => {
    setDisplayName('');
    setPhone('');
    setCreated(null);
    setSaving(false);
  };

  const handleClose = () => {
    reset();
    onClose?.();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const nameErr = required(displayName, "Enter the driver's name, e.g. Jane Wambua");
    if (nameErr) {
      toast.warning(nameErr);
      return;
    }
    const phoneErr = required(phone, 'Enter a Kenyan mobile, e.g. 0712345678');
    if (phoneErr) {
      toast.warning(phoneErr);
      return;
    }
    setSaving(true);
    try {
      const res = await dispatchAPI.createDriver(createDriverPayload({ displayName, phone }));
      const driver = res.data;
      setCreated(driver);
      toast.success(`${driver.display_name || 'Driver'} added`);
      onCreated?.(driver);
    } catch (error) {
      const msg =
        error.response?.data?.display_name?.[0]
        || error.response?.data?.phone?.[0]
        || error.response?.data?.detail
        || error.response?.data?.error
        || 'Could not add driver';
      toast.error(typeof msg === 'string' ? msg : 'Could not add driver');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid="add-driver-dialog">
      <div className="w-full max-w-md rounded-lg border bg-background shadow-lg">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="text-lg font-semibold">{created ? 'Driver added' : 'Add delivery driver'}</h2>
          <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
            Close
          </Button>
        </div>
        {created ? (
          <div className="space-y-3 p-4 text-sm">
            <p>Share these sign-in details with the driver. They must change the password on first login.</p>
            <p>
              <span className="font-medium">Name:</span> {created.display_name}
            </p>
            <p>
              <span className="font-medium">Username:</span> {created.username}
            </p>
            <p>
              <span className="font-medium">Temporary password:</span>{' '}
              <span data-testid="add-driver-temp-password">{created.temporary_password}</span>
            </p>
            <div className="flex justify-end">
              <Button type="button" onClick={handleClose} data-testid="add-driver-done">
                Done
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-3 p-4">
              <div className="form-group">
                <label htmlFor="driver-display-name">Full name *</label>
                <Input
                  id="driver-display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Jane Wambua"
                  data-testid="add-driver-name"
                />
              </div>
              <div className="form-group">
                <label htmlFor="driver-phone">Phone *</label>
                <Input
                  id="driver-phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="0712345678"
                  data-testid="add-driver-phone"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t px-4 py-3">
              <Button type="button" variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving} data-testid="add-driver-save">
                {saving ? 'Saving…' : 'Add driver'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
