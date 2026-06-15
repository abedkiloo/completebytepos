import { formatWalletBalanceLabel, parseWalletBalance, walletBalanceTone } from '../../utils/walletDisplay';
import { cn } from '../../lib/cn';

const toneClasses = {
  debt: 'text-destructive',
  credit: 'text-emerald-600',
  neutral: 'text-muted-foreground',
};

/**
 * Uniform wallet balance display — negative = debt (red), positive = credit (green).
 */
export function CustomerWalletBalance({ balance, className, showZero = false }) {
  const value = parseWalletBalance(balance);
  if (!showZero && value === 0) {
    return <span className={cn('text-muted-foreground', className)}>—</span>;
  }

  const tone = walletBalanceTone(value);
  return (
    <span className={cn('font-semibold tabular-nums', toneClasses[tone], className)}>
      {formatWalletBalanceLabel(value)}
    </span>
  );
}
