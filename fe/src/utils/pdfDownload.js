/**
 * Authenticated PDF download via axios (same base URL, JWT, refresh as other API calls).
 */

export function buildPdfFilename(prefix, idOrLabel, extension = 'pdf') {
  const safe = String(idOrLabel ?? 'document').replace(/[^\w.-]+/g, '_');
  return `${prefix}_${safe}.${extension}`;
}

export function saveBlobAsFile(blob, filename) {
  if (typeof window === 'undefined' || !blob) {
    return;
  }
  const fileBlob =
    blob instanceof Blob ? blob : new Blob([blob], { type: 'application/pdf' });
  const url = window.URL.createObjectURL(fileBlob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(anchor);
}

async function blobToText(blob) {
  if (typeof blob.text === 'function') {
    return blob.text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

export async function readErrorFromBlob(blob) {
  if (!(blob instanceof Blob)) {
    return 'Failed to download PDF';
  }
  try {
    const text = await blobToText(blob);
    if (!text) return 'Failed to download PDF';
    try {
      const json = JSON.parse(text);
      if (typeof json === 'string') return json;
      if (json.error) {
        return typeof json.error === 'string' ? json.error : JSON.stringify(json.error);
      }
      if (json.detail) {
        return typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      }
      return text.slice(0, 200);
    } catch {
      return text.slice(0, 200) || 'Failed to download PDF';
    }
  } catch {
    return 'Failed to download PDF';
  }
}

/**
 * @param {import('axios').AxiosInstance} apiClient
 * @param {string} path - e.g. `/sales/invoices/3/download_pdf/`
 * @param {string} filename
 */
export async function downloadAuthenticatedPdf(apiClient, path, filename) {
  try {
    const response = await apiClient.get(path, { responseType: 'blob' });
    const contentType = response.headers['content-type'] || '';
    if (contentType.includes('application/json')) {
      const message = await readErrorFromBlob(response.data);
      throw new Error(message);
    }
    if (!(response.data instanceof Blob) || response.data.size === 0) {
      throw new Error('PDF file was empty');
    }
    const type = response.data.type || 'application/pdf';
    const blob =
      type.includes('pdf') || response.data.size > 100
        ? response.data
        : new Blob([response.data], { type: 'application/pdf' });
    saveBlobAsFile(blob, filename);
  } catch (err) {
    if (err.response?.data instanceof Blob) {
      const message = await readErrorFromBlob(err.response.data);
      throw new Error(message);
    }
    if (err.message) {
      throw err;
    }
    throw new Error('Failed to download PDF');
  }
}
