// Toast notification utility
let toastId = 0;
let toastListeners = [];

// Default durations (in milliseconds)
const DEFAULT_DURATIONS = {
  success: 3000,
  error: 8000,      // Errors stay longer - 8 seconds
  warning: 5000,
  info: 4000,
};

export const showToast = (message, type = 'success', duration = null) => {
  const id = ++toastId;
  // Use default duration for type if not specified, or 0 for persistent (manual close only)
  const finalDuration = duration !== null ? duration : DEFAULT_DURATIONS[type] || 3000;
  const toast = { id, message, type, duration: finalDuration };
  
  // Notify all listeners
  toastListeners.forEach(listener => listener(toast));
  
  return id;
};

export const subscribeToToasts = (listener) => {
  toastListeners.push(listener);
  return () => {
    toastListeners = toastListeners.filter(l => l !== listener);
  };
};

// Convenience methods
export const toast = {
  success: (message, duration) => showToast(message, 'success', duration),
  error: (message, duration) => showToast(message, 'error', duration !== undefined ? duration : DEFAULT_DURATIONS.error),
  warning: (message, duration) => showToast(message, 'warning', duration),
  info: (message, duration) => showToast(message, 'info', duration),
};

