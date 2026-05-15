import { useEffect, useMemo, useState } from 'react';
import { getAttractions, getPasses, getLibraries } from '../data/load';
import { AttractionCard } from '../components/AttractionCard';
import { Banner } from '../components/Banner';
import { DatePicker } from '../components/DatePicker';
import { SortDropdown, type SortOption } from '../components/SortDropdown';
import { pickTags, type PickedTag } from '../lib/tag-algorithm';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip } from '../lib/distance';
import { SignInModal } from '../components/SignInModal';
import type { Geo } from '../data/types';

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function AttractionsList() {
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const favorites = useFavorites(s => s.slugs);
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);

  const [signInOpen, setSignInOpen] = useState(false);
  const [date, setDate] = useState(() => todayIso());
  const [sort, setSort] = useState<SortOption>('favorites');
  const [userGeo, setUserGeo] = useState<Geo | null>(null);

  // Sync stores to current user
  useEffect(() => {
    loadCardpack(user?.username ?? null);
    loadFavorites(user?.username ?? null);
  }, [user, loadCardpack, loadFavorites]);

  // Geocode ZIP if present
  useEffect(() => {
    const zip = cardpack.zip;
    if (!zip || zip.length !== 5) { setUserGeo(null); return; }
    let cancelled = false;
    geocodeZip(zip).then(g => { if (!cancelled) setUserGeo(g); });
    return () => { cancelled = true; };
  }, [cardpack.zip]);

  const attractions = useMemo(() => getAttractions(), []);
  const allPasses = useMemo(() => getPasses(), []);
  const libraries = useMemo(() => getLibraries(), []);

  const userCardLibIds = useMemo(() => {
    if (!user) return null;  // guest
    const ids = new Set(Object.keys(cardpack.cards));
    if (ids.size === 0) return null;  // admin/empty: behave like guest for tag picking
    return ids;
  }, [user, cardpack.cards]);

  const isGuestOrEmpty = !user || Object.keys(cardpack.cards).length === 0;

  const passesBySlug = useMemo(() => {
    const m = new Map<string, typeof allPasses>();
    for (const p of allPasses) {
      const arr = m.get(p.attraction_slug) ?? [];
      arr.push(p);
      m.set(p.attraction_slug, arr);
    }
    return m;
  }, [allPasses]);

  // Compute picked tags per attraction
  const rows = useMemo(() => {
    return attractions.map(a => {
      const passes = passesBySlug.get(a.slug) ?? [];
      const tags: PickedTag[] = isGuestOrEmpty ? [] : pickTags({
        passes, libraries, userCardLibIds, date, userGeo,
      });
      return { attraction: a, tags, sourceCount: a.sources.length };
    });
  }, [attractions, passesBySlug, libraries, userCardLibIds, date, userGeo, isGuestOrEmpty]);

  // Sort
  const sortedRows = useMemo(() => {
    const copy = [...rows];
    const isFav = (slug: string) => favorites.has(slug);
    const compareName = (a: typeof copy[0], b: typeof copy[0]) =>
      a.attraction.museum_name.localeCompare(b.attraction.museum_name);

    switch (sort) {
      case 'favorites':
        copy.sort((a, b) => {
          const fa = isFav(a.attraction.slug);
          const fb = isFav(b.attraction.slug);
          if (fa !== fb) return fa ? -1 : 1;
          return compareName(a, b);
        });
        break;
      case 'alpha':
        copy.sort(compareName);
        break;
      case 'distance': {
        // sort by min distance among picked tags (or Infinity)
        const minDist = (r: typeof copy[0]) => {
          let best = Infinity;
          for (const t of r.tags) {
            if (t.distanceMi != null && t.distanceMi < best) best = t.distanceMi;
          }
          return best;
        };
        copy.sort((a, b) => minDist(a) - minDist(b));
        break;
      }
      case 'discount': {
        const rank = (r: typeof copy[0]) => {
          if (r.tags.length === 0) return 99;
          const cls = r.tags[0].pass.discount.class;
          const rankMap: Record<string, number> = {
            free: 0, half: 1, 'percent-off': 2, 'dollar-off': 3, price: 4, discount: 5, unknown: 99,
          };
          return rankMap[cls] ?? 99;
        };
        copy.sort((a, b) => rank(a) - rank(b));
        break;
      }
    }
    // "No passes available" sinks to bottom unless Favorited
    copy.sort((a, b) => {
      const ea = a.tags.length === 0 && !isFav(a.attraction.slug);
      const eb = b.tags.length === 0 && !isFav(b.attraction.slug);
      if (ea !== eb) return ea ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, favorites, sort]);

  return (
    <>
      <Banner onSignInClick={() => setSignInOpen(true)} />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
      <div className="max-w-6xl mx-auto px-4 py-6">
        <h1 className="font-serif" style={{ fontSize: 24, marginBottom: 12, color: 'var(--ink-2)' }}>
          Attractions
        </h1>
        <div style={{ display: 'flex', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
          <DatePicker value={date} onChange={setDate} />
          <SortDropdown value={sort} onChange={setSort} distanceEnabled={!!userGeo} />
        </div>
        <p style={{ color: 'var(--ink-3)', fontSize: 11, marginBottom: 12 }}>
          Showing {sortedRows.length} attractions for {date}
        </p>
        <div>
          {sortedRows.map(r => (
            <AttractionCard
              key={r.attraction.slug}
              attraction={r.attraction}
              pickedTags={r.tags}
              isGuestOrEmpty={isGuestOrEmpty}
              sourceCountForGuest={r.sourceCount}
            />
          ))}
        </div>
      </div>
    </>
  );
}
