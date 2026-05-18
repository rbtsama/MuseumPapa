import { describe, it, expect } from 'vitest';
import { townFromAddress } from './address';

describe('townFromAddress', () => {
  it('returns "<town>, MA" for a full address with 5-digit ZIP', () => {
    expect(townFromAddress('123 Main St, Salem, MA 01970')).toBe('Salem, MA');
  });

  it('returns "<town>, MA" for a no-ZIP address (state-only form)', () => {
    expect(townFromAddress('456 Elm St, Beverly, MA')).toBe('Beverly, MA');
  });

  it('returns empty string when the address does not match any pattern', () => {
    expect(townFromAddress('No state here')).toBe('');
  });
});
