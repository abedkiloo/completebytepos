import { DOMAIN_LABELS, DOMAIN_ORDER } from './moduleDomains';

describe('moduleDomains', () => {
  it('labels every ordered domain', () => {
    DOMAIN_ORDER.forEach((key) => {
      expect(DOMAIN_LABELS[key]).toBeTruthy();
    });
  });
});
