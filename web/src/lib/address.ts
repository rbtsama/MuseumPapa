/**
 * Address utility functions.
 *
 * Single source of truth for address parsing helpers shared across
 * the list-card (AttractionInfoRows) and detail page (AttractionDetail).
 */

/**
 * Extract the town from a US address string and append ", MA".
 *
 * Handles the two common forms present in attractions.json:
 *   "123 Main St, Salem, MA 01970"  → "Salem, MA"
 *   "123 Main St, Salem, MA"        → "Salem, MA"
 *
 * Returns an empty string when neither pattern matches.
 */
export function townFromAddress(addr: string | null | undefined): string {
  if (!addr) return '';
  // Prefer the ZIP-code form — it's more specific and unambiguous.
  const m = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\s+\d{5}/);
  if (m) return `${m[1].trim()}, MA`;
  // Fall back to "Town, ST" without a ZIP.
  const m2 = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\b/);
  return m2 ? `${m2[1].trim()}, MA` : '';
}
