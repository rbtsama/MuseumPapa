import { describe, it, expect } from 'vitest';
import { parseSeasonalWindow, passBlockedByRestrictions } from './restrictions';

describe('parseSeasonalWindow', () => {
  it('handles en-dash, hyphen, and "to" separators', () => {
    expect(parseSeasonalWindow('May–Oct')).toEqual([5, 10]);
    expect(parseSeasonalWindow('Jun-Oct')).toEqual([6, 10]);
    expect(parseSeasonalWindow('May to October')).toEqual([5, 10]);
  });

  it('returns null on unparseable input', () => {
    expect(parseSeasonalWindow(null)).toBeNull();
    expect(parseSeasonalWindow('')).toBeNull();
    expect(parseSeasonalWindow('summer')).toBeNull();
    expect(parseSeasonalWindow('whenever')).toBeNull();
  });

  it('parses wrap-around windows (Nov-Feb)', () => {
    expect(parseSeasonalWindow('Nov-Feb')).toEqual([11, 2]);
  });
});

describe('passBlockedByRestrictions', () => {
  it('returns false when restrictions are null', () => {
    expect(passBlockedByRestrictions(null, '2026-05-17')).toBe(false);
  });

  it('blocks weekdays_only passes on Saturday and Sunday', () => {
    const r = { blackout_dates: false, weekdays_only: true, seasonal: null, reservation_required: false };
    expect(passBlockedByRestrictions(r, '2026-05-16')).toBe(true);  // Saturday
    expect(passBlockedByRestrictions(r, '2026-05-17')).toBe(true);  // Sunday
    expect(passBlockedByRestrictions(r, '2026-05-18')).toBe(false); // Monday
    expect(passBlockedByRestrictions(r, '2026-05-22')).toBe(false); // Friday
  });

  it('blocks seasonal passes outside their window', () => {
    const r = { blackout_dates: false, weekdays_only: false, seasonal: 'May–Oct', reservation_required: false };
    expect(passBlockedByRestrictions(r, '2026-06-15')).toBe(false);
    expect(passBlockedByRestrictions(r, '2026-10-31')).toBe(false);
    expect(passBlockedByRestrictions(r, '2026-11-01')).toBe(true);
    expect(passBlockedByRestrictions(r, '2026-04-30')).toBe(true);
  });

  it('does not block on the binary blackout_dates flag (data is too coarse to filter)', () => {
    const r = { blackout_dates: true, weekdays_only: false, seasonal: null, reservation_required: false };
    expect(passBlockedByRestrictions(r, '2026-07-04')).toBe(false);
  });

  it('does not block on reservation_required (date-orthogonal workflow signal)', () => {
    const r = { blackout_dates: false, weekdays_only: false, seasonal: null, reservation_required: true };
    expect(passBlockedByRestrictions(r, '2026-05-17')).toBe(false);
  });
});
