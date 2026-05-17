import type { PassRestrictions } from '../data/types';

const MONTHS: Record<string, number> = {
  jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3, apr: 4, april: 4,
  may: 5, jun: 6, june: 6, jul: 7, july: 7, aug: 8, august: 8,
  sep: 9, sept: 9, september: 9, oct: 10, october: 10,
  nov: 11, november: 11, dec: 12, december: 12,
};

function parseMonthToken(tok: string): number | null {
  const m = tok.trim().toLowerCase().replace(/\.+$/, '');
  return MONTHS[m] ?? null;
}

/** Parse a seasonal window string like "May–Oct" / "Jun-Oct" / "May to October"
 *  into a [startMonth, endMonth] inclusive pair, or null if unparseable.
 *  Wrap-around (e.g. "Nov–Feb") is preserved as startMonth > endMonth.
 */
export function parseSeasonalWindow(s: string | null): [number, number] | null {
  if (!s) return null;
  const norm = s.replace(/[–—−]/g, '-').replace(/\s+to\s+/i, '-');
  const parts = norm.split('-').map(p => p.trim()).filter(Boolean);
  if (parts.length !== 2) return null;
  const start = parseMonthToken(parts[0]);
  const end = parseMonthToken(parts[1]);
  if (start == null || end == null) return null;
  return [start, end];
}

function isWithinSeasonalWindow(date: Date, window: [number, number]): boolean {
  const m = date.getMonth() + 1;
  const [start, end] = window;
  return start <= end ? m >= start && m <= end : m >= start || m <= end;
}

/** True iff the pass cannot be used on the given date because a restriction
 *  rules it out. Date is parsed as a local-time YYYY-MM-DD; weekday in [0..6]
 *  with 0 = Sunday. Restrictions that aren't date-dependent (blackout_dates as
 *  a bare boolean, reservation_required) cannot filter here and are accepted.
 */
export function passBlockedByRestrictions(
  restrictions: PassRestrictions | null,
  isoDate: string,
): boolean {
  if (!restrictions) return false;
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return false;

  if (restrictions.weekdays_only) {
    const dow = d.getDay();
    if (dow === 0 || dow === 6) return true;
  }
  if (restrictions.seasonal) {
    const win = parseSeasonalWindow(restrictions.seasonal);
    if (win && !isWithinSeasonalWindow(d, win)) return true;
  }
  if (restrictions.blackout_dates && restrictions.blackout_dates.includes(isoDate)) {
    return true;
  }
  return false;
}
