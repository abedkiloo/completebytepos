import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind class names (shadcn/ui utility).
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
