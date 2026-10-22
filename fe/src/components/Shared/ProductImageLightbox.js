import React, { useCallback, useEffect, useState } from 'react';
import { Expand, Shrink, ZoomIn } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { cn } from '../../lib/cn';

/**
 * Full-stage product image viewer.
 *
 * Designed for catalogue / POS thumbs: dark stage, image-first, caption
 * with product context, Esc / backdrop / X to dismiss, optional click-to-zoom.
 */
export default function ProductImageLightbox({
  open,
  onOpenChange,
  src,
  alt = '',
  title,
  subtitle,
  meta,
}) {
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    if (!open) setZoomed(false);
  }, [open]);

  const toggleZoom = useCallback(() => {
    setZoomed((z) => !z);
  }, []);

  if (!src) return null;

  const caption = title || alt;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        description={
          caption
            ? `Enlarged product image for ${caption}. Press Escape to close.`
            : 'Enlarged product image. Press Escape to close.'
        }
        className={cn(
          'max-w-[min(56rem,calc(100vw-1.5rem))] gap-0 overflow-hidden border-0',
          'bg-zinc-950 p-0 text-zinc-50 shadow-2xl sm:rounded-xl',
          // Keep close control readable on dark stage
          '[&>button]:text-zinc-200 [&>button]:hover:text-white',
          '[&>button]:ring-offset-zinc-950'
        )}
      >
        <DialogHeader className="sr-only">
          <DialogTitle>{caption || 'Product image'}</DialogTitle>
        </DialogHeader>

        <div className="relative flex max-h-[min(78dvh,40rem)] min-h-[12rem] items-center justify-center overflow-auto bg-zinc-950">
          <button
            type="button"
            onClick={toggleZoom}
            className={cn(
              'block w-full cursor-zoom-in focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40',
              zoomed && 'cursor-zoom-out'
            )}
            aria-label={zoomed ? 'Zoom out' : 'Zoom in'}
          >
            <img
              src={src}
              alt={alt || caption || 'Product'}
              className={cn(
                'mx-auto max-h-[min(78dvh,40rem)] w-auto object-contain transition-transform duration-200',
                zoomed ? 'max-w-none scale-150 origin-center' : 'max-w-full'
              )}
              draggable={false}
            />
          </button>

          <div className="pointer-events-none absolute bottom-3 right-3 flex items-center gap-1.5 rounded-md bg-black/50 px-2 py-1 text-[11px] text-zinc-200 backdrop-blur-sm">
            {zoomed ? (
              <Shrink className="h-3 w-3" aria-hidden />
            ) : (
              <ZoomIn className="h-3 w-3" aria-hidden />
            )}
            <span>{zoomed ? 'Click to zoom out' : 'Click to zoom'}</span>
          </div>
        </div>

        {(caption || subtitle || meta) && (
          <div className="border-t border-white/10 bg-zinc-900/95 px-4 py-3 sm:px-5">
            {caption ? (
              <p className="truncate text-sm font-medium leading-snug text-zinc-50">
                {caption}
              </p>
            ) : null}
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-zinc-400">
              {subtitle ? (
                <span className="font-mono text-[11px] text-zinc-300">{subtitle}</span>
              ) : null}
              {meta ? <span>{meta}</span> : null}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/**
 * Clickable thumbnail that opens {@link ProductImageLightbox}.
 * Use anywhere a product image is shown (list, detail, POS).
 */
export function ProductImageThumb({
  src,
  alt = '',
  title,
  subtitle,
  meta,
  className,
  imgClassName,
  size = 'sm',
  rounded = 'rounded-md',
}) {
  const [open, setOpen] = useState(false);

  if (!src) return null;

  const sizeClass =
    size === 'lg'
      ? 'h-20 w-20'
      : size === 'md'
      ? 'h-14 w-14'
      : 'h-10 w-10';

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen(true);
        }}
        className={cn(
          'group relative shrink-0 overflow-hidden border bg-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'transition-shadow hover:ring-2 hover:ring-primary/40',
          rounded,
          sizeClass,
          className
        )}
        aria-label={`View larger image${title || alt ? ` of ${title || alt}` : ''}`}
      >
        <img
          src={src}
          alt={alt || title || 'Product'}
          className={cn('h-full w-full object-cover', imgClassName)}
          loading="lazy"
          draggable={false}
        />
        <span
          className={cn(
            'pointer-events-none absolute inset-0 flex items-center justify-center',
            'bg-black/0 transition-colors group-hover:bg-black/35 group-focus-visible:bg-black/35'
          )}
          aria-hidden
        >
          <Expand
            className={cn(
              'h-3.5 w-3.5 text-white opacity-0 drop-shadow',
              'transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100',
              size === 'lg' && 'h-5 w-5'
            )}
          />
        </span>
      </button>

      <ProductImageLightbox
        open={open}
        onOpenChange={setOpen}
        src={src}
        alt={alt}
        title={title}
        subtitle={subtitle}
        meta={meta}
      />
    </>
  );
}
