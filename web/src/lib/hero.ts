import type { Attraction } from '../data/types';

/**
 * Canonical 7-class category set. Source of truth for placeholder SVG names.
 * Note: performance and sports don't have a dedicated SVG yet — they fall
 * back to default.svg gracefully (see AVAILABLE_PLACEHOLDERS below).
 */
const CANONICAL_CATEGORIES = [
  'children', 'history', 'nature', 'science', 'art', 'performance', 'sports',
] as const;

// Placeholder SVGs that actually exist in web/public/placeholders/. If a
// canonical category lacks its own SVG, we transparently fall back to default.
const AVAILABLE_PLACEHOLDERS = new Set([
  'children', 'history', 'nature', 'science', 'art',
]);

export function heroSrc(
  attraction: Pick<Attraction, 'categories' | 'hero_image'>,
): string {
  if (attraction.hero_image?.local_path) {
    const filename = attraction.hero_image.local_path.split(/[\\/]/).pop() ?? '';
    if (filename) return `/images/${filename}`;
  }
  const cats = (attraction.categories ?? []).map(c => c.toLowerCase());
  for (const c of cats) {
    if ((CANONICAL_CATEGORIES as readonly string[]).includes(c)) {
      return `/placeholders/${AVAILABLE_PLACEHOLDERS.has(c) ? c : 'default'}.svg`;
    }
  }
  return '/placeholders/default.svg';
}
