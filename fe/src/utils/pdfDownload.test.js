import {
  buildPdfFilename,
  downloadAuthenticatedPdf,
  readErrorFromBlob,
  saveBlobAsFile,
} from './pdfDownload';

describe('pdfDownload', () => {
  it('buildPdfFilename sanitizes labels', () => {
    expect(buildPdfFilename('Invoice', 'INV-001/A')).toBe('Invoice_INV-001_A.pdf');
  });

  it('readErrorFromBlob handles non-blob input', async () => {
    await expect(readErrorFromBlob(null)).resolves.toBe('Failed to download PDF');
  });

  it('readErrorFromBlob parses JSON error', async () => {
    const blob = new Blob([JSON.stringify({ error: 'PDF generation failed' })], {
      type: 'application/json',
    });
    await expect(readErrorFromBlob(blob)).resolves.toBe('PDF generation failed');
  });

  it('readErrorFromBlob parses detail field', async () => {
    const blob = new Blob([JSON.stringify({ detail: 'Not found' })], {
      type: 'application/json',
    });
    await expect(readErrorFromBlob(blob)).resolves.toBe('Not found');
  });

  it('readErrorFromBlob falls back for non-json', async () => {
    const blob = new Blob(['Server error'], { type: 'text/plain' });
    await expect(readErrorFromBlob(blob)).resolves.toBe('Server error');
  });

  it('downloadAuthenticatedPdf surfaces API error blob', async () => {
    const apiClient = {
      get: jest.fn().mockRejectedValue({
        response: {
          data: new Blob([JSON.stringify({ error: 'Forbidden' })], {
            type: 'application/json',
          }),
        },
      }),
    };
    await expect(
      downloadAuthenticatedPdf(apiClient, '/x/', 'a.pdf')
    ).rejects.toThrow('Forbidden');
  });

  it('downloadAuthenticatedPdf rejects json success payload', async () => {
    const apiClient = {
      get: jest.fn().mockResolvedValue({
        data: new Blob([JSON.stringify({ error: 'Not a PDF' })], {
          type: 'application/json',
        }),
        headers: { 'content-type': 'application/json' },
      }),
    };
    await expect(
      downloadAuthenticatedPdf(apiClient, '/x/', 'a.pdf')
    ).rejects.toThrow('Not a PDF');
  });

  it('downloadAuthenticatedPdf rejects empty pdf', async () => {
    const apiClient = {
      get: jest.fn().mockResolvedValue({
        data: new Blob([], { type: 'application/pdf' }),
        headers: { 'content-type': 'application/pdf' },
      }),
    };
    await expect(
      downloadAuthenticatedPdf(apiClient, '/x/', 'a.pdf')
    ).rejects.toThrow('PDF file was empty');
  });

  it('downloadAuthenticatedPdf wraps unknown errors', async () => {
    const apiClient = { get: jest.fn().mockRejectedValue({}) };
    await expect(
      downloadAuthenticatedPdf(apiClient, '/x/', 'a.pdf')
    ).rejects.toThrow('Failed to download PDF');
  });

  it('readErrorFromBlob returns default for empty text', async () => {
    const blob = new Blob([''], { type: 'application/json' });
    await expect(readErrorFromBlob(blob)).resolves.toBe('Failed to download PDF');
  });

  it('downloadAuthenticatedPdf saves pdf blob from axios', async () => {
    const click = jest.fn();
    const anchor = { click, href: '', download: '' };
    jest.spyOn(document, 'createElement').mockReturnValue(anchor);
    Object.defineProperty(document.body, 'appendChild', { value: jest.fn(), configurable: true });
    Object.defineProperty(document.body, 'removeChild', { value: jest.fn(), configurable: true });
    window.URL.createObjectURL = jest.fn(() => 'blob:dl');
    window.URL.revokeObjectURL = jest.fn();

    const apiClient = {
      get: jest.fn().mockResolvedValue({
        data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
        headers: { 'content-type': 'application/pdf' },
      }),
    };

    await downloadAuthenticatedPdf(apiClient, '/sales/invoices/1/download_pdf/', 'Invoice_X.pdf');

    expect(apiClient.get).toHaveBeenCalledWith('/sales/invoices/1/download_pdf/', {
      responseType: 'blob',
    });
    expect(anchor.download).toBe('Invoice_X.pdf');
    expect(click).toHaveBeenCalled();
  });

  it('saveBlobAsFile triggers download link', () => {
    const click = jest.fn();
    const append = jest.fn();
    const remove = jest.fn();
    const revoke = jest.fn();
    const anchor = { click, href: '', download: '' };
    jest.spyOn(document, 'createElement').mockReturnValue(anchor);
    Object.defineProperty(document.body, 'appendChild', { value: append, configurable: true });
    Object.defineProperty(document.body, 'removeChild', { value: remove, configurable: true });
    window.URL.createObjectURL = jest.fn(() => 'blob:mock');
    window.URL.revokeObjectURL = revoke;

    saveBlobAsFile(new Blob(['%PDF-1.4'], { type: 'application/pdf' }), 'test.pdf');

    expect(anchor.download).toBe('test.pdf');
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith('blob:mock');
  });
});
