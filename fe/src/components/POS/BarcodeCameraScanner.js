import React, { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { Camera, X } from 'lucide-react';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { normalizeScanCode } from '../../utils/posBarcodeScan';

const READER_ID = 'pos-barcode-camera-reader';

/**
 * Phone-camera barcode overlay for Retail POS.
 *
 * Works in a normal mobile browser over HTTPS (or localhost). Decoded text is
 * passed to ``onScan`` — the parent looks up the product and adds to cart.
 * Bluetooth HID guns do not use this dialog; they type into the search box.
 *
 * @param {object} props
 * @param {boolean} props.open
 * @param {() => void} props.onClose
 * @param {(code: string) => void|Promise<void>} props.onScan
 */
export default function BarcodeCameraScanner({ open, onClose, onScan }) {
  const scannerRef = useRef(null);
  const handlingRef = useRef(false);
  const [error, setError] = useState('');
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!open) return undefined;

    let cancelled = false;
    let scanner = null;

    async function start() {
      setError('');
      setStarting(true);
      handlingRef.current = false;
      try {
        scanner = new Html5Qrcode(READER_ID, { verbose: false });
        scannerRef.current = scanner;
        await scanner.start(
          { facingMode: 'environment' },
          {
            fps: 8,
            qrbox: { width: 260, height: 140 },
            aspectRatio: 1.777,
          },
          async (decoded) => {
            const code = normalizeScanCode(decoded);
            if (!code || handlingRef.current || cancelled) return;
            handlingRef.current = true;
            try {
              await onScan(code);
            } finally {
              // Allow the next distinct scan after the parent debounce window.
              setTimeout(() => {
                handlingRef.current = false;
              }, 500);
            }
          },
          () => {}
        );
      } catch (err) {
        if (!cancelled) {
          setError(
            err?.message ||
              'Camera unavailable. Allow camera permission, use HTTPS, or type/scan into the search box.'
          );
        }
      } finally {
        if (!cancelled) setStarting(false);
      }
    }

    start();

    return () => {
      cancelled = true;
      const active = scannerRef.current;
      scannerRef.current = null;
      if (active) {
        active
          .stop()
          .then(() => active.clear())
          .catch(() => {});
      }
    };
  }, [open, onScan]);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-md gap-3 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Scan with phone camera
          </DialogTitle>
          <DialogDescription className="text-left text-sm leading-relaxed">
            Point at the barcode. Level 1 — normal phone, no extra hardware.
            Later you can pair a Bluetooth scanner that types into the search
            box (same cart).
          </DialogDescription>
        </DialogHeader>

        <div
          id={READER_ID}
          className="overflow-hidden rounded-md border bg-black min-h-[220px]"
        />

        {starting && !error ? (
          <p className="text-sm text-muted-foreground">Starting camera…</p>
        ) : null}
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            <X className="mr-1 h-4 w-4" />
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
