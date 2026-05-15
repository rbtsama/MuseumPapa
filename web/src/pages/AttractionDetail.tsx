import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { PassTag } from '../components/PassTag';
import { FavoriteButton } from '../components/FavoriteButton';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { formatPriceLine } from '../lib/price-fallback';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import type { Geo, Pass, Library } from '../data/types';

function days(start: string, n: number): string[] {
  const out: string[] = [];
  const d = new Date(start);
  for (let i = 0; i < n; i++) {
    const dd = new Date(d);
    dd.setDate(d.getDate() + i);
    out.push(`${dd.getFullYear()}-${String(dd.getMonth()+1).padStart(2,'0')}-${String(dd.getDate()).padStart(2,'0')}`);
  }
  return out;
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

interface Row {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  available: boolean;
}

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  const user = useAuth(s => s.currentUser);
  const cardpack = useCardpack(s => s.pack);
  const loadCardpack = useCardpack(s => s.load);
  const loadFavorites = useFavorites(s => s.load);
  const [userGeo, setUserGeo] = useState<Geo | null>(null);
  const [startDate, setStartDate] = useState(() => todayIso());
  const [windowSize, setWindowSize] = useState(7);
  const [bookingPass, setBookingPass] = useState<Pass | null>(null);

  useEffect(() => {
    loadCardpack(user?.username ?? null);
    loadFavorites(user?.username ?? null);
  }, [user, loadCardpack, loadFavorites]);

  useEffect(() => {
    if (!cardpack.zip || cardpack.zip.length !== 5) { setUserGeo(null); return; }
    let cancelled = false;
    geocodeZip(cardpack.zip).then(g => { if (!cancelled) setUserGeo(g); });
    return () => { cancelled = true; };
  }, [cardpack.zip]);

  const attraction = useMemo(() => slug ? getAttractionBySlug(slug) : undefined, [slug]);
  const allPasses = useMemo(() => slug ? getPassesForAttraction(slug) : [], [slug]);
  const libraries = useMemo(() => getLibraries(), []);
  const libById = useMemo(() => new Map(libraries.map(l => [l.id, l])), [libraries]);

  if (!slug) return <div className="max-w-6xl mx-auto px-4 py-6">Missing slug.</div>;
  if (!attraction) return <div className="max-w-6xl mx-auto px-4 py-6">Attraction "{slug}" not found.</div>;

  const userCardLibIds = (user && Object.keys(cardpack.cards).length > 0)
    ? new Set(Object.keys(cardpack.cards))
    : null;

  const dateList = days(startDate, windowSize);

  const rowsForDate = (date: string): Row[] => {
    const rows: Row[] = [];
    for (const pass of allPasses) {
      const library = libById.get(pass.library_id);
      if (!library) continue;
      const userCanUse = !userCardLibIds || userCardLibIds.has(pass.library_id);
      if (userCardLibIds && !userCanUse) continue;
      const availStatus = pass.availability?.[date];
      const available = availStatus === 'available' || availStatus === undefined;
      const dist = userGeo && library.geo ? haversineMiles(userGeo, library.geo) : null;
      rows.push({ pass, library, distanceMi: dist, available });
    }
    return rows;
  };

  const rank: Record<string, number> = {
    free: 0, half: 1, 'percent-off': 2, 'dollar-off': 3, price: 4, discount: 5, unknown: 99,
  };
  const sortRows = (rows: Row[]) => {
    return [...rows].sort((a, b) => {
      const ra = rank[a.pass.discount.class] ?? 99;
      const rb = rank[b.pass.discount.class] ?? 99;
      if (ra !== rb) return ra - rb;
      if (a.distanceMi == null && b.distanceMi != null) return 1;
      if (a.distanceMi != null && b.distanceMi == null) return -1;
      if (a.distanceMi != null && b.distanceMi != null) return a.distanceMi - b.distanceMi;
      return a.library.id.localeCompare(b.library.id);
    });
  };

  const heroSrc = (() => {
    if (attraction.hero_image?.local_path) {
      const filename = attraction.hero_image.local_path.split(/[\\/]/).pop() ?? '';
      if (filename) return `/images/${filename}`;
    }
    const cat = attraction.categories?.[0]?.toLowerCase() ?? 'default';
    const known = ['family','children','history','nature','art','science','ocean','recreation'];
    return `/placeholders/${known.includes(cat) ? cat : 'default'}.svg`;
  })();

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
        <FavoriteButton slug={attraction.slug} />
      </div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <img src={heroSrc} alt="" style={{
          width: 280, height: 210, objectFit: 'cover', borderRadius: 4, background: 'var(--paper)',
        }} />
        <div style={{ flexGrow: 1, minWidth: 280 }}>
          <h1 className="font-serif" style={{ fontSize: 28, color: 'var(--ink-2)', marginBottom: 4 }}>
            {attraction.museum_name}
          </h1>
          <p style={{ color: 'var(--ink-3)', fontSize: 13 }}>
            {attraction.address || 'Address unavailable'}
          </p>
          <p style={{ color: 'var(--ink-3)', fontSize: 12, marginTop: 4 }}>
            Categories: {attraction.categories.join(' · ')}
          </p>
          <p style={{ marginTop: 12, fontSize: 13 }}>
            {formatPriceLine(attraction.original_price, null) || 'Price unavailable'}
          </p>
          {attraction.website && (
            <p style={{ marginTop: 12, fontSize: 13 }}>
              <a href={attraction.website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--g)' }}>
                Visit official site →
              </a>
            </p>
          )}
        </div>
      </div>

      <h2 className="font-serif" style={{ fontSize: 18, marginBottom: 8, color: 'var(--ink-2)' }}>
        Discount options
      </h2>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: 12, color: 'var(--ink-3)' }}>From:</label>
        <input
          type="date"
          value={startDate}
          onChange={e => setStartDate(e.target.value)}
          style={{ padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 4, fontSize: 13 }}
        />
        <label style={{ fontSize: 12, color: 'var(--ink-3)' }}>Window:</label>
        <select
          value={windowSize}
          onChange={e => setWindowSize(parseInt(e.target.value))}
          style={{ padding: '4px 8px', border: '1px solid var(--rule)', borderRadius: 4, fontSize: 13 }}
        >
          <option value={3}>3 days</option>
          <option value={7}>7 days</option>
          <option value={14}>14 days</option>
          <option value={30}>30 days</option>
        </select>
      </div>

      {dateList.map(date => {
        const rows = sortRows(rowsForDate(date).filter(r => r.available));
        return (
          <div key={date} style={{ marginBottom: 16, borderBottom: '1px solid var(--rule)', paddingBottom: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 6 }}>
              {date} · {rows.length} option{rows.length === 1 ? '' : 's'}
            </div>
            {rows.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                No passes available on this day.
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {rows.slice(0, 10).map((r, i) => (
                  <button
                    key={`${r.pass.library_id}-${i}`}
                    onClick={() => setBookingPass(r.pass)}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0 }}
                  >
                    <PassTag
                      passType={r.pass.pass_type}
                      discountLabel={r.pass.discount.label || r.pass.discount.class}
                      libraryTown={r.library.town}
                      distanceMi={r.distanceMi}
                    />
                  </button>
                ))}
                {rows.length > 10 && (
                  <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>+{rows.length - 10} more</span>
                )}
              </div>
            )}
          </div>
        );
      })}

      <h2 className="font-serif" style={{ fontSize: 18, marginTop: 24, marginBottom: 8 }}>
        Participating libraries ({attraction.sources.length})
      </h2>
      <ul style={{ fontSize: 13, color: 'var(--ink-3)' }}>
        {attraction.sources.slice(0, 30).map(libId => {
          const l = libById.get(libId);
          return <li key={libId} style={{ padding: '2px 0' }}>
            {l ? `${l.name} (${l.town})` : libId}
          </li>;
        })}
      </ul>

      <BookingConfirmModal
        pass={bookingPass}
        cardpack={cardpack}
        onClose={() => setBookingPass(null)}
      />
    </div>
  );
}
