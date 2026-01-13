/**
 * Format currency (KES)
 */
export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

/**
 * Format date
 */
export const formatDate = (date) => {
  if (!date) return '';
  return new Date(date).toLocaleDateString('en-KE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

/**
 * Format datetime
 */
export const formatDateTime = (date) => {
  if (!date) return '';
  const d = new Date(date);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${day}/${month}/${year}, ${displayHours}:${minutes} ${ampm}`;
};

/**
 * Format number
 */
export const formatNumber = (number) => {
  return new Intl.NumberFormat('en-KE').format(number || 0);
};

/**
 * Format number in compact notation (e.g., 6K, 1.5M)
 */
export const formatCompactNumber = (number) => {
  if (number === null || number === undefined || isNaN(number)) return '0';
  
  const num = typeof number === 'string' ? parseFloat(number) : number;
  
  if (num === 0) return '0';
  
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  
  if (absNum >= 1000000) {
    return `${sign}${(absNum / 1000000).toFixed(1)}M`;
  } else if (absNum >= 1000) {
    return `${sign}${(absNum / 1000).toFixed(1)}K`;
  }
  
  return `${sign}${Math.round(absNum)}`;
};

/**
 * Format currency in compact notation (e.g., KSh 6K, KSh 1.5M)
 */
export const formatCompactCurrency = (amount) => {
  if (amount === null || amount === undefined || isNaN(amount)) return 'KSh 0';
  
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  
  if (num === 0) return 'KSh 0';
  
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  
  if (absNum >= 1000000) {
    return `${sign}KSh ${(absNum / 1000000).toFixed(1)}M`;
  } else if (absNum >= 1000) {
    return `${sign}KSh ${(absNum / 1000).toFixed(1)}K`;
  }
  
  return `${sign}KSh ${Math.round(absNum)}`;
};

