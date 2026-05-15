import type { Attraction, DayKey, Hours } from '../data/types';

const DAY_ORDER: DayKey[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_LABEL: Record<DayKey, string> = {
  mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun',
};

/** Convert JS Date.getDay() (0 = Sun) to our DayKey. */
export function dayKey(d: Date): DayKey {
  const idx = d.getDay();             // 0=Sun, 1=Mon, ..., 6=Sat
  return idx === 0 ? 'sun' : DAY_ORDER[idx - 1];
}

export function dayKeyOf(iso: string): DayKey {
  return dayKey(new Date(iso + 'T00:00:00'));
}

/** True iff the attraction has explicit hours data marking the given ISO date as Closed. */
export function isClosedOn(attraction: Attraction, iso: string): boolean {
  if (!attraction.hours) return false;
  const day = dayKeyOf(iso);
  const v = attraction.hours.regular_hours[day];
  if (!v) return false;
  return v.toLowerCase() === 'closed';
}

/** Return the human-readable hours string for the given ISO date, or null if unknown. */
export function hoursForDate(attraction: Attraction, iso: string): string | null {
  if (!attraction.hours) return null;
  return attraction.hours.regular_hours[dayKeyOf(iso)] ?? null;
}

/** Iterate weekly hours in display order with friendly labels. */
export function weeklyHoursList(hours: Hours): Array<{ key: DayKey; label: string; value: string }> {
  return DAY_ORDER.map(k => ({
    key: k,
    label: DAY_LABEL[k],
    value: hours.regular_hours[k] ?? '—',
  }));
}
