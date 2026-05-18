import { useEffect, useMemo, useState } from 'react';
import { getAttractions, getPasses, getLibraries } from '../data/load';
import { AttractionCard } from '../components/AttractionCard';
import { Banner } from '../components/Banner';
import { DatePicker } from '../components/DatePicker';
import { FavoritesToggle } from '../components/FavoritesToggle';
import { SortDropdown, type SortOption } from '../components/SortDropdown';
import { SearchBox } from '../components/SearchBox';
import { CategoryDropdown } from '../components/CategoryDropdown';
import { pickTags, type PickedTag } from '../lib/tag-algorithm';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip } from '../lib/distance';
import { SignInModal } from '../components/SignInModal';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { isClosedOn } from '../lib/hours';
import { todayIso, formatFriendlyDate } from '../lib/dates';
import type { Geo, Pass } from '../data/types';

export function AttractionsList() {
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const favoritesLive = useFavorites(s => s.slugs);  // re-renders cards when toggled
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);

  const [signInOpen, setSignInOpen] = useState(false);
  const [date, setDate] = useState(() => todayIso());
  // Default sort is always "Recommended" — it already folds distance in as a
  // secondary signal when a ZIP is available, and adds favorites-first + push
  // no-pass-attractions-to-bottom on top of that. Auto-switching to "Distance"
  // when a ZIP shows up would silently throw away those product signals.
  const [sort, setSort] = useState<SortOption>('recommended');
  const handleSortChange = (v: SortOption) => setSort(v);
  const [category, setCategory] = useState<string>('all');
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [search, setSearch] = useState<string>('');
  const [userGeo, setUserGeo] = useState<Geo | null>(null);
  const [bookingPass, setBookingPass] = useState<Pass | null>(null);

  // Snapshot of favorites used by the SORT logic. Refreshed only when user
  // changes sort/date/category (or first mount). This prevents the list from
  // jumping when the user taps a heart — they don't want the card they just
  // favorited to suddenly vanish to the top.
  const [favSnapshot, setFavSnapshot] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    loadCardpack(user?.username ?? null);
    loadFavorites(user?.username ?? null);
  }, [user, loadCardpack, loadFavorites]);

  useEffect(() => {
    setFavSnapshot(new Set(favoritesLive));
    // Intentionally NOT depending on favoritesLive — we only want to re-snapshot
    // when these "structural" inputs change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort, date, category, favoritesOnly, user]);

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
    if (!user) return null;
    const ids = new Set(Object.keys(cardpack.cards));
    if (ids.size === 0) return null;
    return ids;
  }, [user, cardpack.cards]);

  const cardpackState: 'guest' | 'no_cards' | 'has_cards' =
    !user ? 'guest'
      : Object.keys(cardpack.cards).length === 0 ? 'no_cards'
      : 'has_cards';
  const isGuestOrEmpty = cardpackState !== 'has_cards';

  const passesBySlug = useMemo(() => {
    const m = new Map<string, typeof allPasses>();
    for (const p of allPasses) {
      const arr = m.get(p.attraction_slug) ?? [];
      arr.push(p);
      m.set(p.attraction_slug, arr);
    }
    return m;
  }, [allPasses]);

  const rows = useMemo(() => {
    return attractions.map(a => {
      const passes = passesBySlug.get(a.slug) ?? [];
      const tags: PickedTag[] = isGuestOrEmpty ? [] : pickTags({
        passes, libraries, userCardLibIds, date, userGeo,
      });
      return { attraction: a, tags, sourceCount: a.sources.length };
    });
  }, [attractions, passesBySlug, libraries, userCardLibIds, date, userGeo, isGuestOrEmpty]);

  // Search query — case-insensitive token substring across name, address, categories
  const searchTokens = useMemo(
    () => search.trim().toLowerCase().split(/\s+/).filter(Boolean),
    [search],
  );

  const filteredRows = useMemo(() => {
    let out = rows;
    if (favoritesOnly) {
      out = out.filter(r => favoritesLive.has(r.attraction.slug));
    }
    if (category !== 'all') {
      out = out.filter(r => r.attraction.categories.includes(category));
    }
    if (searchTokens.length > 0) {
      out = out.filter(r => {
        const a = r.attraction;
        const hay = `${a.museum_name} ${a.address} ${a.categories.join(' ')}`.toLowerCase();
        return searchTokens.every(t => hay.includes(t));
      });
    }
    return out;
  }, [rows, category, favoritesOnly, favoritesLive, searchTokens]);

  const sortedRows = useMemo(() => {
    const copy = [...filteredRows];
    const isFav = (slug: string) => favSnapshot.has(slug);
    const cmpName = (a: typeof copy[0], b: typeof copy[0]) =>
      a.attraction.museum_name.localeCompare(b.attraction.museum_name);
    const minDist = (r: typeof copy[0]) => {
      let best = Infinity;
      for (const t of r.tags) {
        if (t.distanceMi != null && t.distanceMi < best) best = t.distanceMi;
      }
      return best;
    };

    switch (sort) {
      case 'recommended':
        copy.sort((a, b) => {
          const fa = isFav(a.attraction.slug);
          const fb = isFav(b.attraction.slug);
          if (fa !== fb) return fa ? -1 : 1;
          if (userGeo) {
            const d = minDist(a) - minDist(b);
            if (d !== 0) return d;
          }
          return cmpName(a, b);
        });
        break;
      case 'alpha':
        copy.sort(cmpName);
        break;
      case 'distance':
        copy.sort((a, b) => minDist(a) - minDist(b));
        break;
    }
    // For Recommended + Distance (where the user expects a "best first" sort),
    // closed-today attractions sink to the bottom — even if otherwise nearby
    // or favorited. A-Z is a literal alphabetical order and stays untouched.
    if (sort !== 'alpha') {
      copy.sort((a, b) => {
        const ca = isClosedOn(a.attraction, date);
        const cb = isClosedOn(b.attraction, date);
        if (ca !== cb) return ca ? 1 : -1;
        return 0;
      });
    }
    // For Recommended only, no-pass attractions sink below open ones (but
    // still above the closed-today rows we just sunk). Stable-sort-friendly.
    if (sort === 'recommended') {
      copy.sort((a, b) => {
        const ea = a.tags.length === 0 && !isFav(a.attraction.slug);
        const eb = b.tags.length === 0 && !isFav(b.attraction.slug);
        if (ea !== eb) return ea ? 1 : -1;
        return 0;
      });
    }
    return copy;
  }, [filteredRows, favSnapshot, sort, userGeo]);

  return (
    <>
      <Banner onSignInClick={() => setSignInOpen(true)} />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />

      {/* Sticky filter strip — pinned to viewport just under the TopBar.
          Background opaque so card content scrolling underneath doesn't show through.
          top: 48px ≈ TopBar height; small visual gap is acceptable. */}
      <div
        className="sticky px-3 sm:px-6 py-3"
        style={{
          top: 48,
          zIndex: 40,
          background: 'var(--bg)',
          borderBottom: '1px solid var(--rule)',
        }}
      >
        <div className="max-w-6xl mx-auto">
          <div className="flex gap-2 mb-2 items-center">
            <SearchBox value={search} onChange={setSearch} />
            <DatePicker value={date} onChange={setDate} />
          </div>
          <div className="flex gap-2 items-center flex-wrap">
            <SortDropdown value={sort} onChange={handleSortChange} distanceEnabled={!!userGeo} />
            <CategoryDropdown attractions={attractions} value={category} onChange={setCategory} />
            <FavoritesToggle
              active={favoritesOnly}
              count={favoritesLive.size}
              onToggle={() => setFavoritesOnly(v => !v)}
            />
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-3 sm:px-6 py-3 sm:py-4">
        <p className="mb-3" style={{ color: 'var(--ink-3)', fontSize: 11 }}>
          Showing {sortedRows.length} attractions for {formatFriendlyDate(date)}
        </p>
        <div>
          {sortedRows.map(r => (
            <AttractionCard
              key={r.attraction.slug}
              attraction={r.attraction}
              pickedTags={r.tags}
              cardpackState={cardpackState}
              date={date}
              closedToday={isClosedOn(r.attraction, date)}
              onBookPass={setBookingPass}
              onSignInClick={() => setSignInOpen(true)}
            />
          ))}
        </div>
      </div>
      <BookingConfirmModal
        pass={bookingPass}
        library={bookingPass ? (libraries.find(l => l.id === bookingPass.library_id) ?? null) : null}
        cardpack={cardpack}
        onClose={() => setBookingPass(null)}
      />
    </>
  );
}
