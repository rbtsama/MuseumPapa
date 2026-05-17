import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { PassTypeLabel } from '../components/PassTypeLabel';
import { CouponLine } from '../components/CouponLine';
import { passBlockedByRestrictions } from '../lib/restrictions';
import { GuestLockedRow } from '../components/GuestLockedRow';
import { SignInModal } from '../components/SignInModal';
import { FavoriteButton } from '../components/FavoriteButton';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { couponRank } from '../lib/tag-algorithm';
import type { OriginalPrice } from '../data/types';

function formatOriginalAdult(op: OriginalPrice | null): string {
  const adult = op?.age_pricing?.adult?.price;
  const free = op?.age_pricing?.free_under_age;
  const suffix = free != null ? ` · kids <${free} free` : '';
  if (adult != null) return `Original Adult $${adult}${suffix}`;
  if (free != null) return `Kids <${free} free`;
  return 'Price unavailable';
}
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { weeklyHoursList } from '../lib/hours';
import { heroSrc } from '../lib/hero';
import { todayIso } from '../lib/dates';
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
  const [signInOpen, setSignInOpen] = useState(false);

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

  const userCardLibIds = useMemo(
    () => (user && Object.keys(cardpack.cards).length > 0)
      ? new Set(Object.keys(cardpack.cards))
      : null,
    [user, cardpack.cards],
  );

  const dateList = useMemo(() => days(startDate, windowSize), [startDate, windowSize]);

  const rowsForDate = useMemo(() => (date: string): Row[] => {
    const rows: Row[] = [];
    for (const pass of allPasses) {
      const library = libById.get(pass.library_id);
      if (!library) continue;
      const userCanUse = !userCardLibIds || userCardLibIds.has(pass.library_id);
      if (userCardLibIds && !userCanUse) continue;
      if (passBlockedByRestrictions(pass.restrictions, date)) continue;
      const availStatus = pass.availability?.[date];
      const available = availStatus === 'available' || availStatus === undefined;
      const dist = userGeo && library.geo ? haversineMiles(userGeo, library.geo) : null;
      rows.push({ pass, library, distanceMi: dist, available });
    }
    return rows;
  }, [allPasses, libById, userCardLibIds, userGeo]);

  const sortRows = useMemo(() => (rows: Row[]) => {
    return [...rows].sort((a, b) => {
      const ra = couponRank(a.pass.coupon);
      const rb = couponRank(b.pass.coupon);
      if (ra !== rb) return ra - rb;
      if (a.distanceMi == null && b.distanceMi != null) return 1;
      if (a.distanceMi != null && b.distanceMi == null) return -1;
      if (a.distanceMi != null && b.distanceMi != null) return a.distanceMi - b.distanceMi;
      return a.library.id.localeCompare(b.library.id);
    });
  }, []);

  const heroImg = useMemo(
    () => attraction ? heroSrc(attraction) : '/placeholders/default.svg',
    [attraction],
  );

  if (!slug) return <div className="max-w-6xl mx-auto px-4 py-6">Missing slug.</div>;
  if (!attraction) return <div className="max-w-6xl mx-auto px-4 py-6">Attraction "{slug}" not found.</div>;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
        <FavoriteButton slug={attraction.slug} />
      </div>
      <div style={{ display: 'flex', gap: 24, marginBottom: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <img src={heroImg} alt="" style={{
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
          {attraction.description && (
            <p style={{ marginTop: 12, fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.55 }}>
              {attraction.description}
            </p>
          )}
          <p style={{ marginTop: 12, fontSize: 13 }}>
            {formatOriginalAdult(attraction.original_price)}
          </p>
          {attraction.phone && (
            <p style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-3)' }}>
              📞 <a
                href={`tel:${attraction.phone.replace(/[^\d+]/g, '')}`}
                style={{ color: 'var(--g)' }}
              >{attraction.phone}</a>
            </p>
          )}
          {attraction.website && (
            <p style={{ marginTop: 8, fontSize: 13 }}>
              <a href={attraction.website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--g)' }}>
                Visit official site →
              </a>
            </p>
          )}
        </div>
      </div>

      {attraction.hours && attraction.hours.status === 'varies' && (
        <div className="mb-6 rounded-md p-3"
          style={{ border: '1px solid var(--rule)', background: 'var(--white)' }}>
          <div className="flex items-center gap-2 mb-1">
            <span aria-hidden style={{ fontSize: 14, color: 'var(--ink-3)' }}>🕘</span>
            <h2 className="font-serif" style={{ fontSize: 16, color: 'var(--ink-2)' }}>Hours vary by location</h2>
          </div>
          {attraction.hours.notes && (
            <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>{attraction.hours.notes}</p>
          )}
        </div>
      )}

      {attraction.hours && attraction.hours.status !== 'varies' && attraction.hours.regular_hours && (
        <div className="mb-6 rounded-md p-3"
          style={{ border: '1px solid var(--rule)', background: 'var(--white)' }}>
          <div className="flex items-center gap-2 mb-2">
            <span aria-hidden style={{ fontSize: 14, color: 'var(--ink-3)' }}>🕘</span>
            <h2 className="font-serif" style={{ fontSize: 16, color: 'var(--ink-2)' }}>Hours</h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-7 gap-x-3 gap-y-1">
            {weeklyHoursList(attraction.hours).map(row => {
              const isClosed = row.value.toLowerCase() === 'closed';
              return (
                <div key={row.key} className="flex sm:flex-col items-baseline sm:items-start gap-1 sm:gap-0.5">
                  <span style={{ fontSize: 11, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {row.label}
                  </span>
                  <span style={{
                    fontSize: 12, fontWeight: 500,
                    color: isClosed ? 'var(--rd)' : 'var(--ink-2)',
                  }}>
                    {row.value}
                  </span>
                </div>
              );
            })}
          </div>
          {attraction.hours.notes && (
            <p className="mt-2" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              {attraction.hours.notes}
            </p>
          )}
        </div>
      )}

      <h2 className="font-serif" style={{ fontSize: 18, marginBottom: 8, color: 'var(--ink-2)' }}>
        Available coupons
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
          onChange={e => setWindowSize(parseInt(e.target.value, 10))}
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
              {date} · {rows.length} coupon{rows.length === 1 ? '' : 's'} available
            </div>
            {rows.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                No passes available on this day.
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {rows.slice(0, 10).map((r, i) => {
                  if (!user) {
                    return (
                      <GuestLockedRow
                        key={`${r.pass.library_id}-${i}`}
                        pass={r.pass}
                        library={r.library}
                        onSignInRequest={() => setSignInOpen(true)}
                      />
                    );
                  }
                  const isDigital = r.pass.pass_type === 'digital';
                  return (
                    <button
                      key={`${r.pass.library_id}-${i}`}
                      type="button"
                      onClick={() => setBookingPass(r.pass)}
                      className="flex items-center gap-2 rounded-md text-left"
                      style={{
                        background: 'var(--white)',
                        border: '1px solid var(--rule)',
                        padding: '8px 12px',
                        cursor: 'pointer',
                      }}
                    >
                      <PassTypeLabel type={r.pass.pass_type} />
                      <span style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500 }}>
                        {isDigital ? r.library.name : r.library.town}
                        {!isDigital && r.distanceMi != null && (
                          <span style={{ fontSize: 11, color: 'var(--ink-3)', fontWeight: 400 }}>
                            {' '}· {Math.round(r.distanceMi)} mi
                          </span>
                        )}
                      </span>
                      <span className="ml-auto">
                        <CouponLine coupon={r.pass.coupon} />
                      </span>
                    </button>
                  );
                })}
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
        library={bookingPass ? (libById.get(bookingPass.library_id) ?? null) : null}
        cardpack={cardpack}
        onClose={() => setBookingPass(null)}
      />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </div>
  );
}
