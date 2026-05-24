import type { Library, ResidencyRestriction, VisitorEligibility, Restrictions, Attraction, Pass } from '../data/types';
import { getLibrary } from '../data/load';
import { isMaZip } from '../data/townZips';

export interface LayerResult { ok: boolean; reason?: string; warn?: boolean; }

export function checkL1Card(lib: Library, heldLibraryIds: string[]): LayerResult {
  if (heldLibraryIds.includes(lib.id)) return { ok: true };
  const heldNetworks = new Set(
    heldLibraryIds.map(id => getLibrary(id)?.network).filter(Boolean) as string[]
  );
  if (heldNetworks.has(lib.network)) return { ok: true };
  return { ok: false, reason: `No ${lib.network} network card` };
}

export function checkL3Residency(rr: ResidencyRestriction, lib: Library, homeZip: string): LayerResult {
  if (rr.restricted === 'no') return { ok: true };
  if (rr.restricted === 'unknown') return { ok: true, warn: true, reason: 'Pass pickup eligibility not confirmed' };
  // restricted === 'yes'. We can't verify residency without a home ZIP — warn rather than block.
  if (!homeZip) return { ok: true, warn: true, reason: 'Add your home ZIP to confirm residency' };
  if (rr.scope === 'town') {
    return lib.resident_zips.includes(homeZip)
      ? { ok: true }
      : { ok: false, reason: `${lib.town} passes are for ${lib.town} residents only` };
  }
  if (rr.scope === 'ma') {
    return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: 'This pass is for MA residents only' };
  }
  return { ok: true, warn: true };
}

export function checkL4VisitorResidency(ve: VisitorEligibility | null | undefined, homeZip: string): LayerResult {
  if (!ve || ve.residency === 'none') return { ok: true };
  if (ve.residency === 'unknown') return { ok: true, warn: true, reason: 'Visitor eligibility not confirmed' };
  // Without a home ZIP we can't verify residency — warn rather than block.
  if (!homeZip) return { ok: true, warn: true, reason: 'Add your home ZIP to confirm residency' };
  if (ve.residency === 'ma_resident') return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: 'This attraction admits MA residents only' };
  // town_resident: scope is the town name; we only have ZIP -> can't verify town precisely -> warn-pass
  return { ok: true, warn: true, reason: `This attraction may be ${ve.scope ?? 'local'}-residents only — please verify` };
}

const WD = ['sundays','mondays','tuesdays','wednesdays','thursdays','fridays','saturdays'];
export function checkL8Restrictions(r: Restrictions | null, date: Date): LayerResult {
  if (!r) return { ok: true };
  const m = date.getUTCMonth() + 1, d = date.getUTCDate(), dow = date.getUTCDay();
  for (const b of r.blackout) if (b.month === m && (b.day == null || b.day === d)) return { ok: false, reason: 'Blackout date' };
  if (r.blackout_recurring.includes(WD[dow])) return { ok: false, reason: 'Not available on this weekday' };
  if (r.weekdays_only && (dow === 0 || dow === 6)) return { ok: false, reason: 'Weekdays only' };
  if (r.seasonal) { const { start_month, end_month } = r.seasonal; const inSeason = start_month <= end_month ? (m >= start_month && m <= end_month) : (m >= start_month || m <= end_month); if (!inSeason) return { ok: false, reason: 'Seasonal closure' }; }
  return { ok: true };
}
export function checkL10Availability(av: Record<string,string>, isoDate: string): LayerResult {
  const s = av[isoDate];
  if (s === 'available') return { ok: true };
  if (s == null) return { ok: true, warn: true, reason: 'Availability unknown for this date' };
  return { ok: false, reason: s === 'booked' ? 'Fully booked on this date' : 'Not bookable on this date' };
}

export interface User { homeZip: string; heldLibraryIds: string[]; }
export interface PassVerdict { eligible: boolean; blockedLayer?: string; reasons: string[]; warnings: string[]; }

export function resolvePass(pass: Pass, lib: Library, attr: Attraction, user: User, date?: Date): PassVerdict {
  const reasons: string[] = [], warnings: string[] = [];
  const layers: [string, LayerResult][] = [
    ['L1', checkL1Card(lib, user.heldLibraryIds)],
    ['L3', checkL3Residency(pass.residency_restriction, lib, user.homeZip)],
    ['L4', checkL4VisitorResidency(attr.visitor_eligibility, user.homeZip)],
  ];
  if (date) {
    layers.push(['L8', checkL8Restrictions(pass.restrictions, date)]);
    const iso = date.toISOString().slice(0, 10);
    layers.push(['L10', checkL10Availability(pass.availability, iso)]);
  }
  for (const [name, r] of layers) {
    if (r.warn && r.reason) warnings.push(r.reason);
    if (!r.ok) return { eligible: false, blockedLayer: name, reasons: [r.reason ?? name], warnings };
  }
  return { eligible: true, reasons, warnings };
}
