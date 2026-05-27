import townZipsJson from '../../../config/town_zips.json';
const towns = (townZipsJson as { towns: Record<string, string[]> }).towns;
/** ZIPs of our ~59 seed library towns. NOT the full MA universe — use only for
 *  matching a specific town's residents (see `townZips`), never as "is this MA". */
export const MA_ZIPS: Set<string> = new Set(Object.values(towns).flat());
/**
 * True for any real Massachusetts ZIP. MA occupies the 010xx–027xx range
 * (028xx–029xx is Rhode Island, 030xx+ is NH/ME). Deliberately NOT keyed off
 * MA_ZIPS — that only holds our ~59 seed towns, so genuine MA residents in any
 * other town (e.g. 01886 Westford) were wrongly blocked as "MA residents only".
 */
export const isMaZip = (zip: string): boolean => {
  if (!/^\d{5}$/.test(zip)) return false;
  const prefix = Number(zip.slice(0, 3));
  return prefix >= 10 && prefix <= 27;
};
export const townZips = (town: string): string[] => towns[town] ?? [];
