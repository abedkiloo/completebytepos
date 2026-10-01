import {
  buildReceiptShareCaption,
  canShareFiles,
  captureReceiptPng,
  customerPhoneDigits,
  dataUrlToBlob,
  dataUrlToUint8Array,
  isShareAbort,
  looksLikePngBytes,
  receiptPngFileName,
  shareOrDownloadReceiptPng,
  whatsAppTextUrl,
} from './receiptSnapshotShare';

const PNG_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
const PNG_DATA_URL = `data:image/png;base64,${PNG_B64}`;

describe('receiptSnapshotShare', () => {
  it('detects png magic bytes and rejects short or non-png data', () => {
    expect(looksLikePngBytes(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 1, 2, 3, 4]))).toBe(true);
    expect(looksLikePngBytes(new Uint8Array([0xff, 0xd8, 0xff]))).toBe(false);
    expect(looksLikePngBytes(new Uint8Array([1, 2, 3]))).toBe(false);
    expect(looksLikePngBytes(null)).toBe(false);
  });

  it('builds a png filename from the sale number', () => {
    expect(receiptPngFileName({ sale_number: 'SALE/7' })).toBe('receipt-SALE-7.png');
    expect(receiptPngFileName({ id: 9 })).toBe('receipt-9.png');
    expect(receiptPngFileName({})).toBe('receipt-receipt.png');
    expect(receiptPngFileName({ sale_number: '---' })).toBe('receipt-receipt.png');
  });

  it('uses a thank-you caption without a receipt summary', () => {
    const caption = buildReceiptShareCaption(
      { sale_number: 'S-001', total: '100.00' },
      { storeName: 'Test Duka', phone: '0700' }
    );
    expect(caption).toBe(
      'Thank you for doing business with us. Here is your receipt.'
    );
    expect(caption).not.toContain('S-001');
    expect(caption).not.toContain('Total');
    expect(caption).not.toContain('Test Duka');
    expect(buildReceiptShareCaption({}, {})).toBe(caption);
    expect(buildReceiptShareCaption()).toBe(caption);
  });

  it('reads customer phone digits and builds a WhatsApp text url', () => {
    expect(customerPhoneDigits({ customer_phone: '+254 712 345 678' })).toBe('254712345678');
    expect(customerPhoneDigits({ customer: { phone: '07-11' } })).toBe('0711');
    expect(customerPhoneDigits({})).toBe('');
    expect(customerPhoneDigits()).toBe('');
    expect(whatsAppTextUrl('254712345678', 'Hello')).toBe(
      'https://wa.me/254712345678?text=Hello'
    );
  });

  it('treats AbortError as a cancelled share', () => {
    expect(isShareAbort({ name: 'AbortError' })).toBe(true);
    expect(isShareAbort({ name: 'Error' })).toBe(false);
    expect(isShareAbort(null)).toBe(false);
    expect(isShareAbort(undefined)).toBe(false);
  });

  it('canShareFiles probes the Web Share API and swallows probe failures', () => {
    expect(canShareFiles({ canShare: () => true })).toBe(true);
    expect(canShareFiles({ canShare: () => false })).toBe(false);
    expect(canShareFiles({})).toBe(false);
    expect(canShareFiles(null)).toBe(false);
    expect(typeof canShareFiles()).toBe('boolean');
    expect(
      canShareFiles({
        canShare: () => {
          throw new Error('unsupported');
        },
      })
    ).toBe(false);
    const OriginalFile = global.File;
    delete global.File;
    try {
      expect(canShareFiles({ canShare: () => true })).toBe(false);
    } finally {
      global.File = OriginalFile;
    }
  });

  it('decodes a png data url and rejects non-png payloads', () => {
    const bytes = dataUrlToUint8Array(PNG_DATA_URL);
    expect(looksLikePngBytes(bytes)).toBe(true);
    expect(dataUrlToBlob(PNG_DATA_URL)).toBeInstanceOf(Blob);
    expect(() => dataUrlToUint8Array('data:image/jpeg;base64,AAAA')).toThrow(
      'Could not create receipt photo.'
    );
    expect(() => dataUrlToUint8Array(null)).toThrow('Could not create receipt photo.');
    expect(() => dataUrlToUint8Array(12)).toThrow('Could not create receipt photo.');
    expect(() => dataUrlToUint8Array('data:image/png;base64,')).toThrow(
      'Could not create receipt photo.'
    );
    expect(() => dataUrlToUint8Array('')).toThrow('Could not create receipt photo.');
    expect(() => dataUrlToUint8Array('data:image/png;base64,AAAA')).toThrow(
      'Could not create receipt photo.'
    );
    expect(() => dataUrlToUint8Array('data:image/png;base64')).toThrow(
      'Could not create receipt photo.'
    );
  });

  it('decodes png data urls when atob is missing', () => {
    const original = global.atob;
    delete global.atob;
    try {
      const bytes = dataUrlToUint8Array(PNG_DATA_URL);
      expect(looksLikePngBytes(bytes)).toBe(true);
    } finally {
      global.atob = original;
    }
  });

  it('captures a receipt node through toPng', async () => {
    const toPng = jest.fn().mockResolvedValue(PNG_DATA_URL);
    const node = document.createElement('div');
    await expect(captureReceiptPng(node, toPng)).resolves.toBe(PNG_DATA_URL);
    expect(toPng).toHaveBeenCalledWith(
      node,
      expect.objectContaining({ pixelRatio: 3, backgroundColor: '#ffffff' })
    );
    await expect(captureReceiptPng(null, toPng)).rejects.toThrow(
      'Receipt is not on screen yet.'
    );
    await expect(captureReceiptPng(node, null)).rejects.toThrow(
      'Could not create receipt photo.'
    );
    await expect(
      captureReceiptPng(node, jest.fn().mockResolvedValue('data:image/jpeg;base64,AAAA'))
    ).rejects.toThrow('Could not create receipt photo.');
  });

  it('shares png files when the browser allows it', async () => {
    const share = jest.fn().mockResolvedValue(undefined);
    const download = jest.fn();
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: {},
      store: { storeName: 'Duka' },
      shareTarget: { canShare: () => true, share },
      download,
    });
    expect(result.method).toBe('share');
    expect(result.filename).toBe('receipt-receipt.png');
    expect(share).toHaveBeenCalledWith(
      expect.objectContaining({
        text: 'Thank you for doing business with us. Here is your receipt.',
        title: 'Receipt',
        files: [expect.any(File)],
      })
    );
    expect(download).not.toHaveBeenCalled();
  });

  it('downloads the png when file share is unavailable', async () => {
    const download = jest.fn();
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: { sale_number: 'S-2' },
      store: { phone: '0718' },
      shareTarget: { canShare: () => false },
      download,
    });
    expect(result.method).toBe('download');
    expect(download).toHaveBeenCalledWith(expect.any(Blob), 'receipt-S-2.png');
  });

  it('falls back to download when File is unavailable', async () => {
    const download = jest.fn();
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: { sale_number: 'S-3' },
      shareTarget: { canShare: () => true, share: jest.fn() },
      FileCtor: null,
      download,
    });
    expect(result.method).toBe('download');
    expect(download).toHaveBeenCalled();
  });

  it('downloads when canShare is true but share() is missing', async () => {
    const download = jest.fn();
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: { sale_number: 'S-5' },
      shareTarget: { canShare: () => true },
      download,
    });
    expect(result.method).toBe('download');
    expect(download).toHaveBeenCalled();
  });

  it('skips download when no downloader is provided', async () => {
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: { sale_number: 'S-4' },
      shareTarget: {},
      download: null,
    });
    expect(result.method).toBe('download');
  });

  it('uses the browser navigator when no share target is passed', async () => {
    const download = jest.fn();
    const result = await shareOrDownloadReceiptPng({
      pngDataUrl: PNG_DATA_URL,
      sale: { sale_number: 'S-6' },
      download,
    });
    expect(result.method).toBe('download');
    expect(download).toHaveBeenCalled();
  });
});
