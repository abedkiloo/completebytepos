import { renderToStaticMarkup } from 'react-dom/server';
import { THERMAL_RECEIPT_CSS, ThermalReceipt } from './ThermalReceipt';
import React from 'react';

/**
 * Send a receipt straight to the printer without disturbing the visible page.
 *
 * Why an offscreen iframe instead of `window.print()` on the live document:
 *
 *   1. The old approach relied on a chain of `body * { visibility: hidden }`
 *      rules in index.css and a long list of element classes to "unhide" only
 *      the receipt. Every new screen risked silently leaking into the
 *      printout. An isolated iframe has nothing else to show.
 *
 *   2. `window.open(...)` for a print window is blocked as a popup in many
 *      Chrome / Edge configurations. An iframe added to the current document
 *      is not a popup, so it always works.
 *
 *   3. After printing we can yank the iframe out of the DOM, so a second
 *      print of the same receipt is just as fast and there is no residue.
 *
 * Returns a Promise that resolves once the print dialog has been shown
 * (it does NOT wait for the user to confirm — that's not observable).
 */
export function printThermalReceipt({ sale, store, density = '80mm' }) {
  return new Promise((resolve) => {
    const markup = renderToStaticMarkup(
      <ThermalReceipt sale={sale} store={store} />
    );

    const iframe = document.createElement('iframe');
    // Pull the iframe well off-screen rather than display:none — Safari skips
    // print of display:none iframes.
    iframe.setAttribute('aria-hidden', 'true');
    iframe.style.position = 'fixed';
    iframe.style.right = '0';
    iframe.style.bottom = '0';
    iframe.style.width = '0';
    iframe.style.height = '0';
    iframe.style.border = '0';
    iframe.style.visibility = 'hidden';
    document.body.appendChild(iframe);

    const sizeClass = density === '58mm' ? ' receipt-thermal--58mm' : '';
    const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Receipt ${sale?.sale_number ?? ''}</title>
    <style>
      @page {
        size: ${density} auto;
        margin: 0;
      }
      html, body {
        margin: 0;
        padding: 0;
        background: #ffffff;
      }
      ${THERMAL_RECEIPT_CSS}
    </style>
  </head>
  <body>
    <div class="receipt-thermal-print-root">${markup.replace(
      'class="receipt-thermal"',
      `class="receipt-thermal${sizeClass}"`
    )}</div>
  </body>
</html>`;

    const cleanUp = () => {
      try {
        iframe.parentNode && iframe.parentNode.removeChild(iframe);
      } catch (e) {
        /* idempotent — already removed */
      }
    };

    iframe.onload = () => {
      try {
        const win = iframe.contentWindow;
        if (!win) {
          cleanUp();
          resolve(false);
          return;
        }
        win.focus();
        win.print();
        // Give the browser a tick to finish opening the dialog before we
        // remove the iframe. 600 ms is the smallest gap that has worked
        // reliably across Chrome / Safari / Firefox in testing.
        setTimeout(() => {
          cleanUp();
          resolve(true);
        }, 600);
      } catch (e) {
        cleanUp();
        resolve(false);
      }
    };

    // Some browsers will fire onload before we attach to it if the document
    // is empty. Writing to it after attaching guarantees we'll see the load.
    iframe.srcdoc = html;
  });
}
