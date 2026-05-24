import townZipsJson from '../../../config/town_zips.json';
const towns = (townZipsJson as { towns: Record<string, string[]> }).towns;
export const MA_ZIPS: Set<string> = new Set(Object.values(towns).flat());
export const isMaZip = (zip: string): boolean => MA_ZIPS.has(zip);
export const townZips = (town: string): string[] => towns[town] ?? [];
