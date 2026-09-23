import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import StkWaitDialog from './StkWaitDialog';
import { paymentIntentsAPI } from '../../services/api';

jest.mock('../../services/api', () => ({
  paymentIntentsAPI: {
    create: jest.fn(),
    stk: jest.fn(),
    get: jest.fn(),
    query: jest.fn(),
  },
}));

const paidIntent = {
  id: 9,
  status: 'paid',
  mpesa_receipt: 'QHX7K2L9M1',
  invoice_number: 'INV-9',
};

const promptedIntent = {
  id: 9,
  status: 'prompted',
  phone: '0712345678',
};

describe('StkWaitDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    if (global.setInterval.mockRestore) {
      global.setInterval.mockRestore();
    }
  });

  it('does not start an intent while closed', () => {
    render(
      <StkWaitDialog
        open={false}
        onOpenChange={jest.fn()}
        amount={100}
        phone="0712345678"
      />
    );
    expect(paymentIntentsAPI.create).not.toHaveBeenCalled();
  });

  it('sends a prompt and uses the confirmed receipt', async () => {
    paymentIntentsAPI.create.mockResolvedValue({
      data: { id: 9, status: 'created' },
    });
    paymentIntentsAPI.stk.mockResolvedValue({ data: promptedIntent });
    paymentIntentsAPI.get.mockResolvedValue({ data: paidIntent });
    paymentIntentsAPI.query.mockResolvedValue({ data: paidIntent });
    const onPaid = jest.fn();
    const onOpenChange = jest.fn();

    render(
      <StkWaitDialog
        open
        onOpenChange={onOpenChange}
        amount={250}
        phone="0712345678"
        purpose="pos"
        customerId={3}
        customerName="Ada"
        onPaid={onPaid}
      />
    );

    await waitFor(() => {
      expect(paymentIntentsAPI.create).toHaveBeenCalledWith({
        amount: '250.00',
        phone: '0712345678',
        purpose: 'pos',
        customer_id: 3,
        customer_name: 'Ada',
      });
    });
    expect(paymentIntentsAPI.stk).toHaveBeenCalledWith(9);
    expect(await screen.findByRole('button', { name: /Check status/i })).toBeInTheDocument();
    expect(screen.getByText(/Waiting for M-Pesa/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Check status/i }));
    await waitFor(() => {
      expect(paymentIntentsAPI.query).toHaveBeenCalledWith(9);
    });
    expect(await screen.findByText(/Payment confirmed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/QHX7K2L9M1/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /Use this payment/i }));
    expect(onPaid).toHaveBeenCalledWith(paidIntent);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('keeps waiting when a status poll fails', async () => {
    const realSetInterval = global.setInterval;
    jest.spyOn(global, 'setInterval').mockImplementation((fn) => realSetInterval(fn, 0));
    paymentIntentsAPI.create.mockResolvedValue({
      data: { id: 4, status: 'created' },
    });
    paymentIntentsAPI.stk.mockResolvedValue({
      data: { id: 4, status: 'prompted' },
    });
    paymentIntentsAPI.get.mockRejectedValue(new Error('timeout'));
    paymentIntentsAPI.query.mockRejectedValue({
      response: { data: { detail: 'Could not reach Daraja' } },
    });

    render(
      <StkWaitDialog
        open
        onOpenChange={jest.fn()}
        amount={10}
        phone="0700000000"
      />
    );

    await screen.findByText(/Waiting for M-Pesa/i);
    await waitFor(() => {
      expect(paymentIntentsAPI.get).toHaveBeenCalled();
    });
    fireEvent.click(await screen.findByRole('button', { name: /Check status/i }));
    expect(await screen.findAllByText(/Could not reach Daraja/i)).not.toHaveLength(0);
  });

  it('surfaces create failures and closes without paying', async () => {
    paymentIntentsAPI.create.mockRejectedValue({
      response: { data: { error: 'Daraja down' } },
    });
    const onPaid = jest.fn();
    const onOpenChange = jest.fn();

    render(
      <StkWaitDialog
        open
        onOpenChange={onOpenChange}
        amount={10}
        phone="0700000000"
        onPaid={onPaid}
      />
    );

    expect(await screen.findByText(/Could not send prompt/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Daraja down/i).length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole('button', { name: /Close/i })[0]);
    expect(onPaid).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('shows a failure reason when the customer cancels', async () => {
    paymentIntentsAPI.create.mockResolvedValue({
      data: { id: 2, status: 'created' },
    });
    paymentIntentsAPI.stk.mockResolvedValue({
      data: {
        id: 2,
        status: 'failed',
        failure_reason: 'Customer cancelled',
      },
    });

    render(
      <StkWaitDialog
        open
        onOpenChange={jest.fn()}
        amount={10}
        phone="0700000000"
      />
    );

    expect(await screen.findByText(/Payment not completed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Customer cancelled/i).length).toBeGreaterThan(0);
  });

  it('maps API field errors when the prompt cannot be sent', async () => {
    paymentIntentsAPI.create.mockRejectedValue({
      response: { data: { phone: ['Not a Kenyan mobile'] } },
    });

    render(
      <StkWaitDialog
        open
        onOpenChange={jest.fn()}
        amount={10}
        phone="abc"
      />
    );

    expect(await screen.findAllByText(/Not a Kenyan mobile/i)).not.toHaveLength(0);
  });

  it('falls back to the error message when Daraja returns nothing structured', async () => {
    paymentIntentsAPI.create.mockRejectedValue(new Error('network down'));

    render(
      <StkWaitDialog
        open
        onOpenChange={jest.fn()}
        amount={10}
        phone="0712345678"
      />
    );

    expect(await screen.findAllByText(/network down/i)).not.toHaveLength(0);
  });
});
