/**
 * Local-date helpers (browser timezone). All return ISO-style YYYY-MM-DD
 * strings without timezone shift — these are calendar dates, not instants.
 */

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function tomorrowIso(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOWS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

/** Friendly date label: "Today, May 18" / "Tomorrow, May 19" / "Mon, May 18". */
export function formatFriendlyDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const short = `${MONTHS[d.getMonth()]} ${d.getDate()}`;
  if (iso === todayIso()) return `Today, ${short}`;
  if (iso === tomorrowIso()) return `Tomorrow, ${short}`;
  return `${DOWS[d.getDay()]}, ${short}`;
}
