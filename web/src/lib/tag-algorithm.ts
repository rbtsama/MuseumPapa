import type { Pass, Library, Geo, Coupon } from '../data/types';
import { haversineMiles } from './distance';
import { passBlockedByRestrictions } from './restrictions';

export type DiscountRank = number; // lower is better

/** Rank a coupon for sorting (lower is better). Bonus-tier kids-free counts the
 * whole deal as "free" (rank 0); otherwise the primary audience_policies[0]
 * determines the tier. Kept exported because some non-list views still rank
 * coupons (Detail page, audit pages); the list-card flow below no longer uses
 * this signal — distance is the only axis. */
export function couponRank(coupon: Coupon): number {
  const aps = coupon.audience_policies;
  if (!aps || aps.length === 0) return 99;
  if (aps.some(a => a.form === 'free')) return 0;
  const primary = aps[0];
  switch (primary.form) {
    case 'percent-off':
      return (primary.value ?? 0) >= 50 ? 1 : 2;
    case 'dollar-off':       return 3;
    case 'per-person-price': return 4;
    case 'discount':         return 5;
    default:                 return 99;
  }
}

export interface PickedTag {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  userHasCard: boolean;
}

export interface PickTagsInput {
  passes: Pass[];
  libraries: Library[];
  userCardLibIds: Set<string> | null;
  date: string;
  userGeo: Geo | null;
  maxTags?: number;
}

/**
 * Pick the coupons to surface on an attraction's list card.
 *
 * Rules (in order):
 *   1. Drop passes whose library the user does not hold a card for — for the
 *      list-card flow these are unactionable noise. (When userCardLibIds is
 *      null, e.g. an internal preview, every pass is treated as held.)
 *   2. Drop passes that the calendar / restrictions say can't be used on the
 *      requested date.
 *   3. Within each pass_type bucket sort strictly by distance (nearest first)
 *      and take a per-type candidate cap:
 *        - digital            (Email)  : 1
 *        - physical-coupon    (Pickup) : 3
 *        - physical-circ      (Borrow) : 3
 *   4. Merge the per-type pools, sort by distance again, and return at most
 *      `maxTags` (default 3) overall.
 *
 * Coupon-rank / userHasCard sub-orders that earlier versions used are gone:
 * the user wants the closest options regardless of discount tier, and
 * no-card rows are filtered above the sort.
 */
const PER_TYPE_CAP: Record<Pass['pass_type'], number> = {
  digital: 1,
  'physical-coupon': 3,
  'physical-circ': 3,
  unknown: 0,
};

export function pickTags(input: PickTagsInput): PickedTag[] {
  const { passes, libraries, userCardLibIds, date, userGeo } = input;
  const maxTags = input.maxTags ?? 3;
  const libById = new Map(libraries.map(l => [l.id, l]));

  const candidates: PickedTag[] = [];
  for (const pass of passes) {
    const userHasCard = userCardLibIds ? userCardLibIds.has(pass.library_id) : true;
    if (!userHasCard) continue;  // no-card rows hidden entirely

    if (pass.availability) {
      if (pass.availability[date] !== 'available') continue;
    }
    if (passBlockedByRestrictions(pass.restrictions, date)) continue;

    const library = libById.get(pass.library_id);
    if (!library) continue;

    const dist = userGeo && library.geo
      ? haversineMiles(userGeo, library.geo)
      : null;
    candidates.push({ pass, library, distanceMi: dist, userHasCard });
  }

  const distCmp = (a: PickedTag, b: PickedTag) => {
    if (a.distanceMi == null && b.distanceMi == null) return 0;
    if (a.distanceMi == null) return 1;
    if (b.distanceMi == null) return -1;
    return a.distanceMi - b.distanceMi;
  };

  // Per-type pools: nearest-N within each pass type.
  const pool: PickedTag[] = [];
  for (const type of ['digital', 'physical-coupon', 'physical-circ'] as const) {
    const cap = PER_TYPE_CAP[type];
    const slice = candidates
      .filter(c => c.pass.pass_type === type)
      .sort(distCmp)
      .slice(0, cap);
    pool.push(...slice);
  }

  // Final overall cap by distance.
  pool.sort(distCmp);
  return pool.slice(0, maxTags);
}
