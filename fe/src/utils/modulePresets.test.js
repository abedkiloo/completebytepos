import { MODULE_PRESETS, DEFAULT_MODULE_PRESET } from './modulePresets';

describe('modulePresets', () => {
  it('exports known preset ids', () => {
    const ids = MODULE_PRESETS.map((p) => p.id);
    expect(ids).toContain('retail_starter');
    expect(ids).toContain('retail_full');
    expect(DEFAULT_MODULE_PRESET).toBe('retail_starter');
  });
});
