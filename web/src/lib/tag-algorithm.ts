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
 *   3. Per-type candidate cap (the most each type can contribute):
 *        - digital            (Email)  : 1
 *        - physical-coupon    (Pickup) : 3
 *        - physical-circ      (Borrow) : 3
 *      Within each type, candidates are kept in (distance asc, couponRank asc)
 *      order so the strongest "delivery-cost-tied" options bubble up.
 *   4. Concatenate the per-type pools in DELIVERY-COST ORDER:
 *           Email  →  Pickup (near→far)  →  Borrow (near→far)
 *      An Email always outranks any Pickup; any Pickup outranks any Borrow,
 *      regardless of mileage. Within type, distance asc, couponRank asc.
 *   5. Cap at `maxTags` (default 3) overall.
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

  // Within-type sort: distance asc, then couponRank asc as the tiebreaker for
  // same-library / same-distance rows.
  const inTypeCmp = (a: PickedTag, b: PickedTag) => {
    const da = a.distanceMi == null ? Infinity : a.distanceMi;
    const db = b.distanceMi == null ? Infinity : b.distanceMi;
    if (da !== db) return da - db;
    return couponRank(a.pass.coupon) - couponRank(b.pass.coupon);
  };

  // Build the pool in delivery-cost order: Email block, then Pickup block,
  // then Borrow block. Each block is internally sorted by inTypeCmp and
  // truncated to its per-type cap.
  const pool: PickedTag[] = [];
  for (const type of ['digital', 'physical-coupon', 'physical-circ'] as const) {
    const cap = PER_TYPE_CAP[type];
    const slice = candidates
      .filter(c => c.pass.pass_type === type)
      .sort(inTypeCmp)
      .slice(0, cap);
    pool.push(...slice);
  }

  return pool.slice(0, maxTags);
}
