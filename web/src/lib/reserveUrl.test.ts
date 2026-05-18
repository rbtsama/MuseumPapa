import { describe, it, expect } from 'vitest';
import { passUrlForDate } from './reserveUrl';

describe('passUrlForDate', () => {
  it('rewrites Assabet by-museum URLs into by-date URLs', () => {
    const src = 'https://maldenpubliclibrary.assabetinteractive.com/museum-passes/by-museum/the-trustees-of-the-reservations/';
    expect(passUrlForDate(src, '2026-05-18')).toBe(
      'https://maldenpubliclibrary.assabetinteractive.com/museum-passes/by-date/2026-may/18/the-trustees-of-the-reservations/',
    );
  });

  it('uses no leading zero on single-digit days', () => {
    const src = 'https://wakefield.assabetinteractive.com/museum-passes/by-museum/mfa/';
    expect(passUrlForDate(src, '2026-06-05')).toMatch(/\/by-date\/2026-june\/5\/mfa\/$/);
  });

  it('handles month names with > 4 letters', () => {
    const src = 'https://wakefield.assabetinteractive.com/museum-passes/by-museum/mfa/';
    expect(passUrlForDate(src, '2026-12-25')).toMatch(/\/by-date\/2026-december\/25\/mfa\/$/);
  });

  it('leaves LibCal URLs unchanged', () => {
    const src = 'https://bpl.libcal.com/passes/5bf37dc2bee6';
    expect(passUrlForDate(src, '2026-05-18')).toBe(src);
  });

  it('leaves MuseumKey URLs unchanged', () => {
    const src = 'https://www2.museumkey.com/ui/byMuseum/?code=paulma02025&branchID=231#detail4894';
    expect(passUrlForDate(src, '2026-05-18')).toBe(src);
  });

  it('returns original on invalid date', () => {
    const src = 'https://wakefield.assabetinteractive.com/museum-passes/by-museum/mfa/';
    expect(passUrlForDate(src, 'not-a-date')).toBe(src);
  });

  it('returns original when sourceUrl is empty', () => {
    expect(passUrlForDate('', '2026-05-18')).toBe('');
  });
});
