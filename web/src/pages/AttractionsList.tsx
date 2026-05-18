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
import { LandingPromoModal } from '../components/LandingPromoModal';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { isClosedOn } from '../lib/hours';
import { todayIso, formatFriendlyDate } from '../lib/dates';
import { lsGet, lsSet } from '../lib/localStorage';
import type { Geo, Pass } from '../data/types';

const LANDING_PROMO_DISMISS_KEY = 'landing_promo_dismissed_at';
const LANDING_PROMO_REPEAT_MS = 7 * 24 * 3600 * 1000;  // 7-day cooldown

export function AttractionsList() {
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const favoritesLive = useFavorites(s => s.slugs);  // re-renders cards when toggled
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);

  const [signInOpen, setSignInOpen] = useState(false);
  // Landing promo: show to first-time guests until they dismiss; respect a
  // 7-day cooldown so we don't badger them every visit.
  const [landingOpen, setLandingOpen] = useState(false);
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

  // Decide whether to surface the landing promo on this visit. Show for
  // guests (not signed in) unless they dismissed it within the last 7 days.
  // We do this in an effect (not initial state) so the localStorage check
  // happens after hydration and we can react to sign-in/out events too.
  useEffect(() => {
    if (user) { setLandingOpen(false); return; }
    const dismissedAt = lsGet<number>(LANDING_PROMO_DISMISS_KEY, 0);
    const cooledDown = Date.now() - dismissedAt > LANDING_PROMO_REPEAT_MS;
    if (cooledDown) setLandingOpen(true);
  }, [user]);

  const handleLandingClose = () => {
    lsSet(LANDING_PROMO_DISMISS_KEY, Date.now());
    setLandingOpen(false);
  };
  const handleLandingGetStarted = () => {
    setLandingOpen(false);
    setSignInOpen(true);
  };

  const attractions = useMemo(() => getAttractions(), []);
  const allPasses = useMemo(() => getPasses(), []);
  const libraries = useMemo(() => getLibraries(), []);

  // A library card only counts as "held" when the user has actually entered
  // a barcode for it — without the barcode the card is useless on the Book
  // step. Aligns the list-side filter with BookingConfirmModal's hasCard
  // check (was a silent contradiction: green Book button on the card, then
  // "You don't have a card from {X}" in the modal).
  const usableCardLibIds = useMemo(() => {
    if (!user) return null;
    const ids = new Set(
      Object.entries(cardpack.cards)
        .filter(([, card]) => !!card?.barcode)
        .map(([id]) => id)
    );
    if (ids.size === 0) return null;
    return ids;
  }, [user, cardpack.cards]);
  const userCardLibIds = usableCardLibIds;

  const cardpackState: 'guest' | 'no_cards' | 'has_cards' =
    !user ? 'guest'
      : !usableCardLibIds ? 'no_cards'
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
    const cmpName = (a: typeof copy[0], b: typeof copy[0]) =>
      a.attraction.museum_name.localeCompare(b.attraction.museum_name);
    const minDist = (r: typeof copy[0]) => {
      let best = Infinity;
      for (const t of r.tags) {
        if (t.distanceMi != null && t.distanceMi < best) best = t.distanceMi;
      }
      return best;
    };
    // Recommended tier (lower = surface first):
    //   0  has at least one matching coupon for this date
    //   1  no matching coupon, but not closed today either
    //   2  closed on this date
    const recommendedTier = (r: typeof copy[0]) => {
      if (isClosedOn(r.attraction, date)) return 2;
      if (r.tags.length === 0) return 1;
      return 0;
    };

    switch (sort) {
      case 'recommended':
        // Three-tier sort: has-coupons / no-coupons / closed; distance within tier.
        copy.sort((a, b) => {
          const ta = recommendedTier(a);
          const tb = recommendedTier(b);
          if (ta !== tb) return ta - tb;
          const da = minDist(a);
          const db = minDist(b);
          if (da !== db) return da - db;
          return cmpName(a, b);
        });
        break;
      case 'alpha':
        // Literal alphabetical; no tier reordering.
        copy.sort(cmpName);
        break;
      case 'distance':
        copy.sort((a, b) => minDist(a) - minDist(b));
        // Closed-today sinks to the bottom on Distance (open-first principle).
        copy.sort((a, b) => {
          const ca = isClosedOn(a.attraction, date);
          const cb = isClosedOn(b.attraction, date);
          if (ca !== cb) return ca ? 1 : -1;
          return 0;
        });
        break;
    }
    return copy;
  }, [filteredRows, sort, date]);

  return (
    <>
      <Banner onSignInClick={() => setSignInOpen(true)} />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
      <LandingPromoModal
        isOpen={landingOpen}
        onClose={handleLandingClose}
        onGetStarted={handleLandingGetStarted}
      />

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
