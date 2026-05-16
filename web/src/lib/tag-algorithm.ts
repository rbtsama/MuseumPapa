import type { Pass, Library, Geo } from '../data/types';
import { haversineMiles } from './distance';

export type DiscountRank = number; // lower is better

const DISCOUNT_RANK: Record<string, DiscountRank> = {
  free: 0,
  half: 1,
  'percent-off': 2,
  'dollar-off': 3,
  price: 4,
  discount: 5,
  unknown: 99,
};

export interface PickedTag {
  pass: Pass;
  library: Library;
  distanceMi: number | null;  // null if user has no ZIP or no library geo
}

export interface PickTagsInput {
  passes: Pass[];                       // all passes for one attraction
  libraries: Library[];                 // all libraries (will be filtered)
  userCardLibIds: Set<string> | null;   // null = no filter (guest), set = filter to these lib IDs
  date: string;                         // YYYY-MM-DD
  userGeo: Geo | null;                  // ZIP centroid, null = no distance
  maxTags?: number;                     // default 4
}

/**
 * Pick ≤4 tags for one attraction × one day.
 *
 * Order (spec §5.2):
 *   1. Digital (zero distance) — at most 1, highest discount class
 *   2. Physical (sorted by discount desc, distance asc) — fills remaining slots
 *   3. Loan-card (same sort) — fills remaining slots
 *
 * Filters before sorting:
 *   - Pass's library must be in user_cards (if set)
 *   - calendar[date] must be "available"
 */
export function pickTags(input: PickTagsInput): PickedTag[] {
  const { passes, libraries, userCardLibIds, date, userGeo } = input;
  const maxTags = input.maxTags ?? 4;
  const libById = new Map(libraries.map(l => [l.id, l]));

  const candidates: PickedTag[] = [];
  for (const pass of passes) {
    if (userCardLibIds && !userCardLibIds.has(pass.library_id)) continue;
    if (pass.availability && pass.availability[date] !== 'available') continue;
    // If pass has a calendar but date isn't in it, skip (no data)
    if (pass.availability && !(date in pass.availability)) continue;
    const library = libById.get(pass.library_id);
    if (!library) continue;
    const dist = userGeo && library.geo
      ? haversineMiles(userGeo, library.geo)
      : null;
    candidates.push({ pass, library, distanceMi: dist });
  }

  // Split into 3 groups
  const digital = candidates.filter(c => c.pass.pass_type === 'digital');
  const physical = candidates.filter(c => c.pass.pass_type === 'physical-coupon');
  const circ = candidates.filter(c => c.pass.pass_type === 'physical-circ');

  const tagsOut: PickedTag[] = [];

  // 1. Digital: only 1 tag, highest discount (lowest rank). Tie-break by library_id alpha.
  if (digital.length > 0) {
    digital.sort((a, b) => {
      const ra = DISCOUNT_RANK[a.pass.discount.class] ?? 99;
      const rb = DISCOUNT_RANK[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      return a.library.id.localeCompare(b.library.id);
    });
    tagsOut.push(digital[0]);
  }

  const distCmp = (a: PickedTag, b: PickedTag) => {
    if (a.distanceMi == null && b.distanceMi == null) return 0;
    if (a.distanceMi == null) return 1;
    if (b.distanceMi == null) return -1;
    return a.distanceMi - b.distanceMi;
  };

  const sortByDiscThenDist = (group: PickedTag[]) => {
    group.sort((a, b) => {
      const ra = DISCOUNT_RANK[a.pass.discount.class] ?? 99;
      const rb = DISCOUNT_RANK[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      return distCmp(a, b);
    });
  };

  sortByDiscThenDist(physical);
  for (const t of physical) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  sortByDiscThenDist(circ);
  for (const t of circ) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  return tagsOut;
}
