import type { OriginalPrice } from '../data/types';

export function formatOriginalAdult(op: OriginalPrice | null): string {
  const adult = op?.age_pricing?.adult?.price;
  const free = op?.age_pricing?.free_under_age;
  const suffix = free != null ? ` · FREE age<${free}` : '';
  if (adult != null) return `Adult $${adult}${suffix}`;
  if (free != null) return `FREE age<${free}`;
  return 'Price unavailable';
}
