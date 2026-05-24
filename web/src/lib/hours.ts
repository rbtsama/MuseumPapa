import type { Attraction, DayKey, Hours } from '../data/types';

const DAY_ORDER: DayKey[] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const DAY_LABEL: Record<DayKey, string> = {
  monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu',
  friday: 'Fri', saturday: 'Sat', sunday: 'Sun',
};

/** JS Date.getDay() (0=Sun) → full DayKey. */
export function dayKey(d: Date): DayKey {
  const idx = d.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  return idx === 0 ? 'sunday' : DAY_ORDER[idx - 1];
}

export function dayKeyOf(iso: string): DayKey {
  return dayKey(new Date(iso + 'T00:00:00'));
}

/** Convert "HH:MM-HH:MM" to "10:00 AM – 5:00 PM". Returns the raw string for
 *  any value that doesn't match the range pattern (e.g. "closed", "unknown"). */
function formatTimeRange(raw: string): string {
  const m = raw.match(/^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$/);
  if (!m) return raw;
  const fmt = (h: number, min: number) => {
    const period = h < 12 ? 'AM' : 'PM';
    const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${h12}:${String(min).padStart(2, '0')} ${period}`;
  };
  return `${fmt(+m[1], +m[2])} – ${fmt(+m[3], +m[4])}`;
}

/** True iff the attraction explicitly marks the given ISO date as "closed".
 *  Unknown or missing hours are treated as NOT closed — we don't grey out on unknown. */
export function isClosedOn(attraction: Attraction, iso: string): boolean {
  if (!attraction.hours) return false;
  const day = dayKeyOf(iso);
  const v = attraction.hours[day];
  if (!v) return false;
  return v.toLowerCase() === 'closed';
}

/** Return the raw hours string for the given ISO date, or null if unknown/missing. */
export function hoursForDate(attraction: Attraction, iso: string): string | null {
  if (!attraction.hours) return null;
  const v = attraction.hours[dayKeyOf(iso)];
  if (!v || v === 'unknown') return null;
  return v;
}

/** Display info for a date — { value, varies } shape consumed by AttractionInfoRows.
 *  Formats "HH:MM-HH:MM" values to "10:00 AM – 5:00 PM". Returns null when hours
 *  are absent or unknown for that day. */
export function hoursDisplay(attraction: Attraction, iso: string): { value: string; varies: boolean } | null {
  if (!attraction.hours) return null;
  const v = hoursForDate(attraction, iso);
  if (!v) return null;
  return { value: formatTimeRange(v), varies: false };
}

/** Iterate weekly hours in display order with friendly labels.
 *  Used by VisitInfoSection's expandable table. Returns the raw value string
 *  (callers already handle "closed" colouring). */
export function weeklyHoursList(hours: Hours): Array<{ key: DayKey; label: string; value: string }> {
  return DAY_ORDER.map(k => ({
    key: k,
    label: DAY_LABEL[k],
    value: hours[k] ?? '—',
  }));
}
