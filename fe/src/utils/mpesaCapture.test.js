import {
  MPESA_CAPTURE_CODE,
  MPESA_CAPTURE_PROMPT,
  isMpesaCode,
  isMpesaPrompt,
  mpesaCollectingNow,
} from './mpesaCapture';

describe('mpesaCapture', () => {
  it('treats prompt as the default capture mode', () => {
    expect(isMpesaPrompt(MPESA_CAPTURE_PROMPT)).toBe(true);
    expect(isMpesaPrompt(MPESA_CAPTURE_CODE)).toBe(false);
    expect(isMpesaCode(MPESA_CAPTURE_CODE)).toBe(true);
    expect(isMpesaCode(MPESA_CAPTURE_PROMPT)).toBe(false);
    expect(isMpesaCode('anything-else')).toBe(true);
  });

  it('collects now only for M-Pesa with a positive received amount', () => {
    expect(mpesaCollectingNow('cash', { received: 100 })).toBe(false);
    expect(mpesaCollectingNow('mpesa', { creditSale: true, received: 0 })).toBe(false);
    expect(mpesaCollectingNow('mpesa', { received: 0 })).toBe(false);
    expect(mpesaCollectingNow('mpesa', { paid: 50 })).toBe(true);
    expect(mpesaCollectingNow('mpesa', { received: 80 })).toBe(true);
    expect(mpesaCollectingNow('mpesa', { received: 'nope' })).toBe(false);
  });
});
