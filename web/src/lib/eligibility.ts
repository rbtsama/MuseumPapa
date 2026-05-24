import type { Library, ResidencyRestriction, VisitorEligibility } from '../data/types';
import { getLibrary } from '../data/load';
import { isMaZip } from '../data/townZips';

export interface LayerResult { ok: boolean; reason?: string; warn?: boolean; }

export function checkL1Card(lib: Library, heldLibraryIds: string[]): LayerResult {
  if (heldLibraryIds.includes(lib.id)) return { ok: true };
  const heldNetworks = new Set(
    heldLibraryIds.map(id => getLibrary(id)?.network).filter(Boolean) as string[]
  );
  if (heldNetworks.has(lib.network)) return { ok: true };
  return { ok: false, reason: `你没有 ${lib.network} 网络的卡` };
}

export function checkL3Residency(rr: ResidencyRestriction, lib: Library, homeZip: string): LayerResult {
  if (rr.restricted === 'no') return { ok: true };
  if (rr.restricted === 'unknown') return { ok: true, warn: true, reason: '取 pass 资格未确认' };
  // restricted === 'yes'
  if (rr.scope === 'town') {
    return lib.resident_zips.includes(homeZip)
      ? { ok: true }
      : { ok: false, reason: `${lib.town} 仅本镇居民可取此 pass` };
  }
  if (rr.scope === 'ma') {
    return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: '此 pass 仅 MA 居民可取' };
  }
  return { ok: true, warn: true };
}

export function checkL4VisitorResidency(ve: VisitorEligibility | null | undefined, homeZip: string): LayerResult {
  if (!ve || ve.residency === 'none') return { ok: true };
  if (ve.residency === 'unknown') return { ok: true, warn: true, reason: '景点访客资格未确认' };
  if (ve.residency === 'ma_resident') return isMaZip(homeZip) ? { ok: true } : { ok: false, reason: '该景点仅 MA 居民可入' };
  // town_resident: scope is the town name; we only have ZIP -> can't verify town precisely -> warn-pass
  return { ok: true, warn: true, reason: `该景点可能仅 ${ve.scope ?? '本镇'} 居民,建议核对` };
}
