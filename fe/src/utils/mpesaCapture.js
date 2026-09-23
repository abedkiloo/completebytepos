/** How the cashier captures an M-Pesa payment: STK prompt or SMS code. */

export const MPESA_CAPTURE_PROMPT = 'prompt';
export const MPESA_CAPTURE_CODE = 'code';

export function isMpesaPrompt(mode) {
  return mode === MPESA_CAPTURE_PROMPT;
}

export function isMpesaCode(mode) {
  return mode !== MPESA_CAPTURE_PROMPT;
}

/** True when M-Pesa is selected and money is being collected now (not pay-later). */
export function mpesaCollectingNow(method, receivedCheck = {}) {
  if (method !== 'mpesa') return false;
  if (receivedCheck.creditSale) return false;
  const amount = Number(receivedCheck.received ?? receivedCheck.paid);
  return Number.isFinite(amount) && amount > 0;
}
