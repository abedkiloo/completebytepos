import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SystemSettings from './SystemSettings';
import { useStoreSettings } from '../../hooks/useStoreSettings';
import { storeSettingsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { DEFAULT_STORE_SETTINGS } from '../../utils/storeSettingsCache';

jest.mock('../../hooks/useStoreSettings', () => ({
  useStoreSettings: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  storeSettingsAPI: {
    get: jest.fn(),
    update: jest.fn(),
  },
}));

jest.mock('../../utils/toast', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
    info: jest.fn(),
  },
}));

jest.mock('./ModuleSettingsCard', () => () => null);

const settings = {
  ...DEFAULT_STORE_SETTINGS,
  maker_checker_enabled: true,
};

function renderSettings() {
  const applyLocal = jest.fn();
  useStoreSettings.mockReturnValue({ settings, applyLocal });
  return render(<SystemSettings />);
}

describe('SystemSettings backdate limit save', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    storeSettingsAPI.update.mockResolvedValue({ status: 200, data: settings });
  });

  it('saves the past-sale backdate limit without asking for a reason', async () => {
    renderSettings();

    fireEvent.change(screen.getByLabelText(/Past sale backdate limit/i), {
      target: { value: '90' },
    });

    expect(screen.queryByLabelText(/Reason for this settings change/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Save store settings/i }));

    await waitFor(() => {
      expect(storeSettingsAPI.update).toHaveBeenCalledWith({ backfill_max_days: 90 });
    });
    expect(toast.warning).not.toHaveBeenCalledWith(
      'Enter a reason for these store setting changes.'
    );
  });

  it('shows a reason field on the save bar when a sensitive store rule changes', async () => {
    renderSettings();

    fireEvent.change(screen.getByLabelText(/Footer message/i), {
      target: { value: 'Licensed retailer' },
    });

    const reason = await screen.findByLabelText(/Reason for/i);
    expect(reason).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Save store settings/i }));
    expect(storeSettingsAPI.update).not.toHaveBeenCalled();
    expect(toast.warning).toHaveBeenCalledWith(
      'Enter a reason for these store setting changes.'
    );

    fireEvent.change(reason, { target: { value: 'Legal footer update' } });
    fireEvent.click(screen.getByRole('button', { name: /Save store settings/i }));

    await waitFor(() => {
      expect(storeSettingsAPI.update).toHaveBeenCalledWith({
        receipt_footer_text: 'Licensed retailer',
        reason: 'Legal footer update',
      });
    });
  });
});
