import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AddDriverDialog, {
  createDriverPayload,
  splitDriverDisplayName,
} from './AddDriverDialog';
import { dispatchAPI } from '../../services/api';
import { toast } from '../../utils/toast';

jest.mock('../../services/api', () => ({
  dispatchAPI: { createDriver: jest.fn() },
}));

jest.mock('../../utils/toast', () => ({
  toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() },
}));

describe('AddDriverDialog helpers', () => {
  test('splits names and builds payload', () => {
    expect(splitDriverDisplayName('Jane Wambua Kariuki')).toEqual({
      firstName: 'Jane',
      lastName: 'Wambua Kariuki',
    });
    expect(splitDriverDisplayName('Solo')).toEqual({ firstName: 'Solo', lastName: '' });
    expect(splitDriverDisplayName('  ')).toEqual({ firstName: '', lastName: '' });
    expect(createDriverPayload({ displayName: ' Ken ', phone: ' 0712 ' })).toEqual({
      display_name: 'Ken',
      phone: '0712',
    });
  });
});

describe('AddDriverDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('returns null when closed', () => {
    const { container } = render(<AddDriverDialog open={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('validates then creates and shows temp password', async () => {
    const onCreated = jest.fn();
    dispatchAPI.createDriver.mockResolvedValue({
      data: {
        id: 9,
        display_name: 'Jane Wambua',
        username: 'drv12345678',
        temporary_password: 'tmpPass99',
      },
    });
    render(<AddDriverDialog open onClose={jest.fn()} onCreated={onCreated} />);
    fireEvent.click(screen.getByTestId('add-driver-save'));
    expect(toast.warning).toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'Jane Wambua' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    expect(dispatchAPI.createDriver).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    await waitFor(() => expect(dispatchAPI.createDriver).toHaveBeenCalledWith({
      display_name: 'Jane Wambua',
      phone: '0712345678',
    }));
    expect(await screen.findByTestId('add-driver-temp-password')).toHaveTextContent('tmpPass99');
    expect(onCreated).toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('add-driver-done'));
  });

  test('surfaces API errors', async () => {
    dispatchAPI.createDriver.mockRejectedValue({
      response: { data: { phone: ['Enter a Kenyan mobile, e.g. 0718515142'] } },
    });
    render(<AddDriverDialog open onClose={jest.fn()} />);
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'Jane' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '12' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('Enter a Kenyan mobile, e.g. 0718515142'),
    );
  });

  test('generic error fallback', async () => {
    dispatchAPI.createDriver.mockRejectedValue({});
    render(<AddDriverDialog open onClose={jest.fn()} />);
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'Jane' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Could not add driver'));
  });

  test('uses detail and display_name errors', async () => {
    dispatchAPI.createDriver.mockRejectedValueOnce({
      response: { data: { display_name: ['Enter the driver’s name, e.g. Jane Wambua'] } },
    });
    render(<AddDriverDialog open onClose={jest.fn()} />);
    fireEvent.change(screen.getByTestId('add-driver-name'), { target: { value: 'Jane' } });
    fireEvent.change(screen.getByTestId('add-driver-phone'), { target: { value: '0712345678' } });
    fireEvent.click(screen.getByTestId('add-driver-save'));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Enter the driver’s name, e.g. Jane Wambua"),
    );
  });

  test('closes without creating', () => {
    const onClose = jest.fn();
    render(<AddDriverDialog open onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: /^Close$/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
