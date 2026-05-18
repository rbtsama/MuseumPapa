import type { Pass, Library, Geo, Coupon } from '../data/types';
import { haversineMiles } from './distance';
import { passBlockedByRestrictions } from './restrictions';

export type DiscountRank = number; // lower is better

/** Rank a coupon for sorting (lower is better). Bonus-tier kids-free counts the
 * whole deal as "free" (rank 0); otherwise the primary audience_policies[0]
 * determines the tier. */
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

export function pickTags(input: PickTagsInput): PickedTag[] {
  const { passes, libraries, userCardLibIds, date, userGeo } = input;
  const maxTags = input.maxTags ?? 4;
  const libById = new Map(libraries.map(l => [l.id, l]));

  const candidates: PickedTag[] = [];
  for (const pass of passes) {
    // Honest availability: when the pass has a calendar dict, the date must
    // carry an explicit 'available'. `undefined` means we never scraped that
    // date (out-of-window or blank) — don't fake green. When availability is
    // null the pass has no calendar (e.g. MuseumKey, login-only); show it
    // best-effort instead of hiding.
    if (pass.availability) {
      if (pass.availability[date] !== 'available') continue;
    }
    if (passBlockedByRestrictions(pass.restrictions, date)) continue;
    const library = libById.get(pass.library_id);
    if (!library) continue;
    const dist = userGeo && library.geo
      ? haversineMiles(userGeo, library.geo)
      : null;
    const userHasCard = userCardLibIds ? userCardLibIds.has(pass.library_id) : true;
    candidates.push({ pass, library, distanceMi: dist, userHasCard });
  }

  const digital = candidates.filter(c => c.pass.pass_type === 'digital');
  const physical = candidates.filter(c => c.pass.pass_type === 'physical-coupon');
  const circ = candidates.filter(c => c.pass.pass_type === 'physical-circ');

  const tagsOut: PickedTag[] = [];

  // Sort that prioritizes userHasCard, then coupon rank, then distance.
  const distCmp = (a: PickedTag, b: PickedTag) => {
    if (a.distanceMi == null && b.distanceMi == null) return 0;
    if (a.distanceMi == null) return 1;
    if (b.distanceMi == null) return -1;
    return a.distanceMi - b.distanceMi;
  };

  const sortGroup = (group: PickedTag[]) => {
    group.sort((a, b) => {
      if (a.userHasCard !== b.userHasCard) return a.userHasCard ? -1 : 1;
      const ra = couponRank(a.pass.coupon);
      const rb = couponRank(b.pass.coupon);
      if (ra !== rb) return ra - rb;
      return distCmp(a, b);
    });
  };

  if (digital.length > 0) {
    sortGroup(digital);
    tagsOut.push(digital[0]);
  }

  sortGroup(physical);
  for (const t of physical) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  sortGroup(circ);
  for (const t of circ) {
    if (tagsOut.length >= maxTags) break;
    tagsOut.push(t);
  }

  return tagsOut;
}
