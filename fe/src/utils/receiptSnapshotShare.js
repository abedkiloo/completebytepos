import { saveBlobAsFile } from './pdfDownload';

export const RECEIPT_SHARE_CAPTION =
  'Thank you for doing business with us. Here is your receipt.';

const PNG_MAGIC = [0x89, 0x50, 0x4e, 0x47];

export function looksLikePngBytes(bytes) {
  if (!bytes || bytes.length < 4) return false;
  return PNG_MAGIC.every((value, index) => bytes[index] === value);
}

export function receiptPngFileName(sale) {
  const raw = String(sale?.sale_number || sale?.id || 'receipt');
  const safe = raw.replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'receipt';
  return `receipt-${safe}.png`;
}

export function buildReceiptShareCaption() {
  return RECEIPT_SHARE_CAPTION;
}

export function customerPhoneDigits(sale) {
  return String(sale?.customer_phone || sale?.customer?.phone || '').replace(/\D/g, '');
}

export function whatsAppTextUrl(phone, message) {
  return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
}

export function isShareAbort(error) {
  return Boolean(error && error.name === 'AbortError');
}

export function canShareFiles(shareTarget = typeof navigator !== 'undefined' ? navigator : null) {
  if (!shareTarget || typeof shareTarget.canShare !== 'function' || typeof File === 'undefined') {
    return false;
  }
  try {
    const probe = new File(['x'], 'receipt.png', { type: 'image/png' });
    return Boolean(shareTarget.canShare({ files: [probe] }));
  } catch {
    return false;
  }
}

export function dataUrlToUint8Array(dataUrl) {
  if (!dataUrl || typeof dataUrl !== 'string' || !dataUrl.startsWith('data:image/png')) {
    throw new Error('Could not create receipt photo.');
  }
  const comma = dataUrl.indexOf(',');
  const encoded = comma >= 0 ? dataUrl.slice(comma + 1) : '';
  if (!encoded) {
    throw new Error('Could not create receipt photo.');
  }
  const binary = typeof atob === 'function' ? atob(encoded) : Buffer.from(encoded, 'base64').toString('binary');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  if (!looksLikePngBytes(bytes)) {
    throw new Error('Could not create receipt photo.');
  }
  return bytes;
}

export function dataUrlToBlob(dataUrl) {
  const bytes = dataUrlToUint8Array(dataUrl);
  return new Blob([bytes], { type: 'image/png' });
}

export async function captureReceiptPng(node, toPng, options = {}) {
  if (!node) {
    throw new Error('Receipt is not on screen yet.');
  }
  if (typeof toPng !== 'function') {
    throw new Error('Could not create receipt photo.');
  }
  const dataUrl = await toPng(node, {
    pixelRatio: 3,
    cacheBust: true,
    backgroundColor: '#ffffff',
    ...options,
  });
  dataUrlToUint8Array(dataUrl);
  return dataUrl;
}

export async function shareOrDownloadReceiptPng({
  pngDataUrl,
  sale,
  store,
  shareTarget,
  download = saveBlobAsFile,
  FileCtor = typeof File !== 'undefined' ? File : undefined,
} = {}) {
  const blob = dataUrlToBlob(pngDataUrl);
  const filename = receiptPngFileName(sale);
  const caption = buildReceiptShareCaption(sale, store);
  const target = shareTarget || (typeof navigator !== 'undefined' ? navigator : null);
  const canShare = canShareFiles(target) && typeof target?.share === 'function' && FileCtor;

  if (canShare) {
    const file = new FileCtor([blob], filename, { type: 'image/png' });
    await target.share({
      files: [file],
      text: caption,
      title: `Receipt ${sale?.sale_number || ''}`.trim(),
    });
    return { method: 'share', caption, filename };
  }

  if (typeof download === 'function') {
    download(blob, filename);
  }
  return { method: 'download', caption, filename };
}
