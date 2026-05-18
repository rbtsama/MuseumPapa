import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import {
  getAttractionBySlug, getPassesForAttraction, getLibraries,
} from '../data/load';
import { CouponRow } from '../components/CouponRow';
import { CouponCalendar } from '../components/CouponCalendar';
import { HeroBanner } from '../components/detail/HeroBanner';
import { AttractionInfoRows } from '../components/AttractionInfoRows';
import { DescriptionBlock } from '../components/detail/DescriptionBlock';
import { isClosedOn } from '../lib/hours';
import { VisitInfoSection } from '../components/detail/VisitInfoSection';
import { GuestLockedRow } from '../components/GuestLockedRow';
import { SignInModal } from '../components/SignInModal';
import { BookingConfirmModal } from '../components/BookingConfirmModal';
import { passBlockedByRestrictions } from '../lib/restrictions';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { couponRank } from '../lib/tag-algorithm';
import { heroSrc } from '../lib/hero';
import { todayIso } from '../lib/dates';
import type { Geo, Pass, Library } from '../data/types';

interface Row {
  pass: Pass;
  library: Library;
  distanceMi: number | null;
  available: boolean;
  userHasCard: boolean;
}

function townFromAddress(addr: string): string {
  const m = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\s+\d{5}/);
  if (m) return m[1].trim();
  const m2 = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\b/);
  return m2 ? m2[1].trim() : '';
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

  // Same barcode-filter as AttractionsList — a card without a barcode is not
  // yet usable, so it shouldn't surface a pass row or affect the best-deal
  // calculation. Keeps Detail and List consistent.
  const userCardLibIds = useMemo(() => {
    if (!user) return null;
    const ids = new Set(
      Object.entries(cardpack.cards)
        .filter(([, card]) => !!card?.barcode)
        .map(([id]) => id)
    );
    if (ids.size === 0) return null;
    return ids;
  }, [user, cardpack.cards]);

  const dataHorizon = useMemo(() => {
    let max = '';
    for (const p of allPasses) {
      if (!p.availability) continue;
      for (const d in p.availability) if (d > max) max = d;
    }
    return max;
  }, [allPasses]);

  const monthPills = useMemo(() => {
    const out: string[] = [];
    const base = new Date(`${today}T00:00:00`);
    base.setDate(1);
    const horizonMonth = dataHorizon.slice(0, 7);
    for (let i = 0; i < 2; i++) {
      const d = new Date(base);
      d.setMonth(base.getMonth() + i);
      const m = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (horizonMonth && m > horizonMonth) break;
      out.push(m);
      if (!horizonMonth) break; // no scraped data anywhere → only show current month
    }
    return out;
  }, [today, dataHorizon]);

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
      if (passBlockedByRestrictions(pass.restrictions, date)) continue;
      const available = pass.availability === null
        ? true
        : pass.availability[date] === 'available';
      const dist = userGeo && library.geo ? haversineMiles(userGeo, library.geo) : null;
      const userHasCard = userCardLibIds ? userCardLibIds.has(pass.library_id) : true;
      rows.push({ pass, library, distanceMi: dist, available, userHasCard });
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

  const cellInfo = useMemo(() => {
    const out: Record<string, { best: string; isFree: boolean }> = {};
    for (const d of datesOfMonth) {
      // Best deal among rows the user can actually use.
      const rows = rowsForDate(d)
        .filter(r => r.available)
        .filter(r => userCardLibIds === null || r.userHasCard);
      if (rows.length === 0) { out[d] = { best: '', isFree: false }; continue; }
      const sorted = sortRows(rows);
      const top = sorted[0].pass.coupon.audience_policies[0];
      let label = ''; let isFree = false;
      if (top) {
        switch (top.form) {
          case 'free': label = 'FREE'; isFree = true; break;
          case 'percent-off': label = top.value != null ? `${top.value}%` : '%'; break;
          case 'dollar-off': label = top.value != null ? `-$${top.value}` : '$ off'; break;
          case 'per-person-price': label = top.value != null ? `$${top.value}` : '$'; break;
          case 'discount': label = 'disc'; break;
        }
      }
      out[d] = { best: label, isFree };
    }
    return out;
  }, [datesOfMonth, rowsForDate, sortRows, userCardLibIds]);

  // Selected day's rows — HIDE no-card rows entirely (do not dim).
  const selectedDayRows = useMemo(
    () => sortRows(
      rowsForDate(selectedDate)
        .filter(r => r.available)
        .filter(r => userCardLibIds === null || r.userHasCard),
    ),
    [selectedDate, rowsForDate, sortRows, userCardLibIds],
  );

  if (!slug) return <div className="max-w-3xl mx-auto p-4">Missing slug.</div>;
  if (!attraction) return <div className="max-w-3xl mx-auto p-4">Attraction "{slug}" not found.</div>;

  const town = townFromAddress(attraction.address);

  return (
    <div className="max-w-3xl mx-auto" style={{ background: 'var(--white)', minHeight: '100vh' }}>
      <HeroBanner
        imageSrc={heroImg}
        museumName={attraction.museum_name}
        town={town}
        favoriteSlug={attraction.slug}
      />

      {attraction.categories.length > 0 && (
        <div style={{ padding: '14px 14px 0' }}>
          {attraction.categories.map(c => (
            <span key={c} style={{
              display: 'inline-block', padding: '2px 8px', borderRadius: 10,
              background: 'var(--paper)', color: 'var(--ink-3)',
              fontSize: 10, fontWeight: 500, marginRight: 4, marginBottom: 4,
            }}>{c}</span>
          ))}
        </div>
      )}

      <section style={{ padding: '12px 14px', borderBottom: '1px solid var(--rule)' }}>
        <AttractionInfoRows
          attraction={attraction}
          date={today}
          closedToday={isClosedOn(attraction, today)}
        />
      </section>

      <DescriptionBlock description={attraction.description} />

      {/* Coupon / perks section — green tint to mark product UVP */}
      <section style={{ padding: 14, background: 'var(--g-pale)', borderBottom: '1px solid var(--rule)' }}>
        <h3 style={{
          margin: '0 0 8px', fontSize: 13, fontWeight: 600,
          color: 'var(--g)', textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>Your perks · what it'll cost you</h3>

        <div className="flex gap-1.5 mb-3">
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

        <div style={{ marginTop: 12 }}>
          {selectedDayRows.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No coupons available on this date
            </div>
          ) : (
            selectedDayRows.slice(0, 10).map((r, i) => {
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
              return (
                <CouponRow
                  key={`${r.pass.library_id}-${i}`}
                  pass={r.pass}
                  library={r.library}
                  distanceMi={r.distanceMi}
                  userHasCard={r.userHasCard}
                  showTopBorder={i > 0}
                  onBook={setBookingPass}
                />
              );
            })
          )}
          {selectedDayRows.length > 10 && (
            <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 6 }}>
              +{selectedDayRows.length - 10} more
            </div>
          )}
        </div>
      </section>

      <VisitInfoSection attraction={attraction} />

      <BookingConfirmModal
        pass={bookingPass}
        library={bookingPass ? (libById.get(bookingPass.library_id) ?? null) : null}
        cardpack={cardpack}
        selectedDate={selectedDate}
        onClose={() => setBookingPass(null)}
      />
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </div>
  );
}
