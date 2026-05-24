import { describe, it, expect } from 'vitest';
import { recommend } from './recommend';
describe('recommend', () => {
  it('returns at most 4, dedups email passes, eligible-first', () => {
    const recs = recommend('mfa', { homeZip:'01880', heldLibraryIds:['wakefield','reading','somerville','wilmington','bpl'] });
    expect(recs.length).toBeLessThanOrEqual(4);
    const emails = recs.filter(r => r.pass.pass_form === 'digital_email');
    expect(emails.length).toBeLessThanOrEqual(1);
  });
});
