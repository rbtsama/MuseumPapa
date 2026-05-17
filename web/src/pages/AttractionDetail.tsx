import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { PassTypeLabel } from '../components/PassTypeLabel';
import { CouponLine } from '../components/CouponLine';
import { CouponCalendar } from '../components/CouponCalendar';
import { MuseumReservationBanner } from '../components/MuseumReservationBanner';
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
  const suffix = free != null ? ` · FREE age<${free}` : '';
  if (adult != null) return `Adult $${adult}${suffix}`;
  if (free != null) return `FREE age<${free}`;
  return 'Price unavailable';
}
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { weeklyHoursList } from '../lib/hours';
import { heroSrc } from '../lib/hero';
import { todayIso } from '../lib/dates';
import type { Geo, Pass, Library } from '../data/types';


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
  const today = useMemo(() => todayIso(), []);
  const [month, setMonth] = useState(() => today.slice(0, 7));
  const [selectedDate, setSelectedDate] = useState<string>(today);
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

  // Six-month pill row starting from today's month
  const monthPills = useMemo(() => {
    const out: string[] = [];
    const base = new Date(`${today}T00:00:00`);
    base.setDate(1);
    for (let i = 0; i < 6; i++) {
      const d = new Date(base);
      d.setMonth(base.getMonth() + i);
      out.push(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
    }
    return out;
  }, [today]);

  // Dates in the currently-selected month (1..lastDay).
  const datesOfMonth = useMemo(() => {
    const [yStr, mStr] = month.split('-');
    const year = Number(yStr); const m = Number(mStr);
    const lastDay = new Date(year, m, 0).getDate();
    return Array.from({ length: lastDay }, (_, i) =>
      `${yStr}-${mStr}-${String(i + 1).padStart(2, '0')}`,
    );
  }, [month]);

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

  // Best coupon per date in the visible month — what the user actually wants
  // to see at a glance. "FREE" beats "50%" beats "$5", etc.
  const cellInfo = useMemo(() => {
    const out: Record<string, { best: string; isFree: boolean }> = {};
    for (const d of datesOfMonth) {
      const rows = rowsForDate(d).filter(r => r.available);
      if (rows.length === 0) { out[d] = { best: '', isFree: false }; continue; }
      const sorted = sortRows(rows);
      const top = sorted[0].pass.coupon.audience_policies[0];
      let label = '';
      let isFree = false;
      if (top) {
        switch (top.form) {
          case 'free':
            label = 'FREE'; isFree = true; break;
          case 'percent-off':
            label = top.value != null ? `${top.value}%` : '%'; break;
          case 'dollar-off':
            label = top.value != null ? `-$${top.value}` : '$ off'; break;
          case 'per-person-price':
            label = top.value != null ? `$${top.value}` : '$'; break;
          case 'discount':
            label = 'disc'; break;
        }
      }
      out[d] = { best: label, isFree };
    }
    return out;
  }, [datesOfMonth, rowsForDate, sortRows]);

  // Selected day's passes, sorted.
  const selectedDayRows = useMemo(
    () => sortRows(rowsForDate(selectedDate).filter(r => r.available)),
    [selectedDate, rowsForDate, sortRows],
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
          <h1 className="font-serif" style={{ fontSize: 22, color: 'var(--ink-2)', marginBottom: 4}}>
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
                Visit museum's website →
              </a>
            </p>
          )}
        </div>
      </div>

      {attraction.hours && attraction.hours.status === 'varies' && (
        <div className="mb-6 rounded-md p-3"
          style={{ border: '1px solid var(--rule)', background: 'var(--white)' }}>
          <div className="flex items-center gap-2 mb-1">
            <span aria-hidden style={{ fontSize: 13, color: 'var(--ink-3)' }}>🕘</span>
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
            <span aria-hidden style={{ fontSize: 13, color: 'var(--ink-3)' }}>🕘</span>
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

      <div style={{ marginBottom: 14 }}>
        <MuseumReservationBanner
          reservation={attraction.museum_reservation}
          attractionName={attraction.museum_name}
          variant="detail"
        />
      </div>
      <h2 className="font-serif" style={{ fontSize: 16, marginBottom: 8, color: 'var(--ink-2)' }}>
        Available coupons
      </h2>

      <div className="flex flex-wrap gap-1.5 mb-3">
        {monthPills.map(m => {
          const active = m === month;
          const d = new Date(`${m}-01T00:00:00`);
          const lbl = d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
          return (
            <button
              key={m}
              type="button"
              onClick={() => setMonth(m)}
              className="rounded-md whitespace-nowrap"
              style={{
                padding: '4px 10px', fontSize: 12, fontWeight: 500,
                background: active ? 'var(--g)' : 'transparent',
                color: active ? 'var(--white)' : 'var(--ink-2)',
                border: `1px solid ${active ? 'var(--g)' : 'var(--rule)'}`,
                cursor: 'pointer',
              }}
            >{lbl}</button>
          );
        })}
      </div>

      <div className="mb-4">
        <CouponCalendar
          month={month}
          selectedDate={selectedDate}
          todayIso={today}
          cellInfo={cellInfo}
          onSelect={setSelectedDate}
        />
      </div>

      <div style={{ fontSize: 13, color: 'var(--ink-3)', marginBottom: 8 }}>
        {new Date(`${selectedDate}T00:00:00`).toLocaleDateString('en-US', {
          weekday: 'long', month: 'short', day: 'numeric',
        })}
        {' · '}
        {selectedDayRows.length} coupon{selectedDayRows.length === 1 ? '' : 's'} available
      </div>
      {selectedDayRows.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic', marginBottom: 16 }}>
          No coupons available on this date
        </div>
      ) : (
        <div className="flex flex-col gap-1.5 mb-4">
          {selectedDayRows.slice(0, 10).map((r, i) => {
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
          {selectedDayRows.length > 10 && (
            <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>+{selectedDayRows.length - 10} more</span>
          )}
        </div>
      )}

      <h2 className="font-serif" style={{ fontSize: 16, marginTop: 24, marginBottom: 8 }}>
        Participating libraries ({attraction.sources.length})
      </h2>
      <ul style={{ fontSize: 13, color: 'var(--ink-3)' }}>
        {attraction.sources.slice(0, 30).map(libId => {
          const l = libById.get(libId);
          return <li key={libId} style={{ padding: '2px 0' }}>
            {l ? `${l.name} · ${l.town}` : libId}
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
