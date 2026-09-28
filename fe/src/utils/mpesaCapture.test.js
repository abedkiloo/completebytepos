import {
  MPESA_CAPTURE_CODE,
  MPESA_CAPTURE_PROMPT,
  MPESA_PROMPT_COMING_SOON,
  announceMpesaPromptComingSoon,
  isLiveMpesaPrompt,
  isMpesaCode,
  isMpesaPrompt,
  mpesaCollectingNow,
  mpesaPromptIsLive,
} from './mpesaCapture';
import { toast } from './toast';

jest.mock('./toast', () => ({
  toast: { info: jest.fn(), warning: jest.fn(), error: jest.fn(), success: jest.fn() },
}));

describe('mpesaCapture', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('treats prompt and code as distinct capture modes', () => {
    expect(isMpesaPrompt(MPESA_CAPTURE_PROMPT)).toBe(true);
    expect(isMpesaPrompt(MPESA_CAPTURE_CODE)).toBe(false);
    expect(isMpesaCode(MPESA_CAPTURE_CODE)).toBe(true);
    expect(isMpesaCode(MPESA_CAPTURE_PROMPT)).toBe(false);
    expect(isMpesaCode('anything-else')).toBe(true);
    expect(MPESA_PROMPT_COMING_SOON).toBe(true);
    expect(mpesaPromptIsLive()).toBe(false);
    expect(isLiveMpesaPrompt(MPESA_CAPTURE_PROMPT)).toBe(false);
    expect(announceMpesaPromptComingSoon()).toBe('Coming soon');
    expect(toast.info).toHaveBeenCalledWith('Coming soon');
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
