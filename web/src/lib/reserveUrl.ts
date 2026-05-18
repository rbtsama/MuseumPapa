/**
 * Build the per-date reservation URL a "Book" click should land the user on.
 *
 * Assabet (52 libraries / 89% of passes) exposes per-museum reservation pages
 * at /museum-passes/by-museum/<slug>/ AND per-date reservation forms at
 *     /museum-passes/by-date/<YYYY-monthname>/<DD>/<slug>/
 * The by-date form is already filled in with the chosen date so the user
 * doesn't have to scroll the calendar themselves. When we know the user's
 * selected date, deep-link straight into that form.
 *
 * LibCal and MuseumKey URLs don't share this convention — return unchanged.
 *
 * @param sourceUrl  pass.source_url (already normalized to the per-museum form
 *                   for Assabet by build/catalog.py)
 * @param isoDate    YYYY-MM-DD the user picked
 * @returns          the per-date URL when Assabet + valid date; otherwise the
 *                   original sourceUrl
 */
export function passUrlForDate(sourceUrl: string, isoDate: string): string {
  const m = sourceUrl.match(
    /^(https?:\/\/[^/]+\.assabetinteractive\.com)\/museum-passes\/by-museum\/([^/?#]+)\/?$/,
  );
  if (!m) return sourceUrl;

  const [, origin, slug] = m;
  const d = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return sourceUrl;

  const monthName = d.toLocaleString('en-US', { month: 'long' }).toLowerCase();
  const year = d.getFullYear();
  const day = d.getDate();  // no leading zero — matches Assabet URL grammar

  return `${origin}/museum-passes/by-date/${year}-${monthName}/${day}/${slug}/`;
}
