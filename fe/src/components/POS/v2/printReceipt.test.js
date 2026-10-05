import { waitFor } from '@testing-library/react';

import { printThermalReceipt } from './printReceipt';
import { DEFAULT_BRAND_LOGO } from '../../../utils/storeBranding';

const sale = { sale_number: 'SALE-1', items: [], total: '0', amount_paid: '0' };
const store = { storeName: 'Omuwenga Suppliers' };

function stubImage(outcome) {
  global.Image = class {
    set src(value) {
      setTimeout(() => (outcome === 'load' ? this.onload() : this.onerror()));
    }
  };
}

describe('printThermalReceipt logo', () => {
  const RealImage = global.Image;
  afterEach(() => {
    global.Image = RealImage;
    document.body.innerHTML = '';
  });

  async function printedHtml(receiptLogoUrl) {
    printThermalReceipt({ sale, store: { ...store, receiptLogoUrl } });
    let iframe;
    await waitFor(() => {
      iframe = document.querySelector('iframe');
      expect(iframe).toBeTruthy();
    });
    return iframe.srcdoc;
  }

  it('prints the uploaded logo once it loads', async () => {
    stubImage('load');
    expect(await printedHtml('/media/receipt/brand.png')).toContain('src="/media/receipt/brand.png"');
  });

  it('prints the packaged logo when the uploaded one cannot load', async () => {
    stubImage('error');
    const html = await printedHtml('http://backend:8000/media/receipt/brand.png');
    expect(html).toContain(`src="${DEFAULT_BRAND_LOGO}"`);
    expect(html).not.toContain('backend:8000');
  });

  it('prints no logo when receipts hide it', async () => {
    expect(await printedHtml(null)).not.toContain('<img');
  });
});
