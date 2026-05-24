import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router';
import {
  getAttractionBySlug, getLibrary, getLibraries,
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
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';
import { useFavorites } from '../stores/favorites';
import { geocodeZip, haversineMiles } from '../lib/distance';
import { heroSrc } from '../lib/hero';
import { todayIso } from '../lib/dates';
import { recommend, type RecommendedPass } from '../lib/recommend';
import { couponSummary } from '../lib/couponSummary';
import type { User } from '../lib/eligibility';
import type { Geo, Pass } from '../data/types';

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  const authUser = useAuth(s => s.currentUser);
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
    loadCardpack(authUser?.username ?? null);
    loadFavorites(authUser?.username ?? null);
  }, [authUser, loadCardpack, loadFavorites]);

  useEffect(() => {
    if (!cardpack.zip || cardpack.zip.length !== 5) { setUserGeo(null); return; }
    let cancelled = false;
    geocodeZip(cardpack.zip).then(g => { if (!cancelled) setUserGeo(g); });
    return () => { cancelled = true; };
  }, [cardpack.zip]);

  const attraction = useMemo(() => slug ? getAttractionBySlug(slug) : undefined, [slug]);
  const libraries = useMemo(() => getLibraries(), []);
  const libById = useMemo(() => new Map(libraries.map(l => [l.id, l])), [libraries]);

  // Barcode-filter: a card without a barcode is not usable.
  const userCardLibIds = useMemo(() => {
    if (!authUser) return null;
    const ids = new Set(
      Object.entries(cardpack.cards)
        .filter(([, card]) => !!card?.barcode)
        .map(([id]) => id)
    );
    if (ids.size === 0) return null;
    return ids;
  }, [authUser, cardpack.cards]);

  // Build eligibility user for the engine.
  const engineUser = useMemo((): User => ({
    homeZip: cardpack.zip ?? '',
    heldLibraryIds: userCardLibIds ? Array.from(userCardLibIds) : [],
  }), [cardpack.zip, userCardLibIds]);

  // Guest user for ordering locked rows (all will be L1-blocked, ordered by coupon strength).
  const guestUser = useMemo((): User => ({ homeZip: '', heldLibraryIds: [] }), []);

  // Compute available data horizon (for calendar month pills).
  const dataHorizon = useMemo(() => {
    if (!slug) return '';
    let max = '';
    const recs = recommend(slug, guestUser);
    for (const r of recs) {
      for (const d in r.pass.availability) if (d > max) max = d;
    }
    return max;
  }, [slug, guestUser]);

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
      if (!horizonMonth) break;
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

  const heroImg = useMemo(
    () => attraction ? heroSrc(attraction) : '/placeholders/default.svg',
    [attraction],
  );

  // Selected day recs via the engine — show up to 4, eligible first.
  const selectedDayRecs = useMemo((): RecommendedPass[] => {
    if (!slug) return [];
    return recommend(slug, engineUser, new Date(`${selectedDate}T00:00:00`));
  }, [slug, engineUser, selectedDate]);

  // Calendar cellInfo — reflect the ACTUAL availability of the best candidate pass.
  // Strategy: call recommend() WITHOUT a date to get the candidate pass the user would use
  // on an available day (L8/L10 skipped). Then, per visible date, read that pass's
  // availability[d] to derive status. This keeps the calendar honest.
  const cellInfo = useMemo(() => {
    const out: Record<string, { best: string; isFree: boolean; status: 'available' | 'booked' | 'closed' | 'none' }> = {};
    if (!slug) return out;

    // Find candidate pass: best pass for this user ignoring per-date availability.
    // Top of recommend() without date = highest-scored pass (eligible by L1/L3/L4).
    const candidateRecs = recommend(slug, engineUser); // no date → L8/L10 skipped
    const candidateRec = candidateRecs.find(r => r.verdict.eligible) ?? candidateRecs[0] ?? null;

    if (!candidateRec) {
      // No passes at all (guest with no cards, or attraction has no passes).
      for (const d of datesOfMonth) out[d] = { best: '', isFree: false, status: 'none' };
      return out;
    }

    const candidatePass = candidateRec.pass;
    const summary = couponSummary(candidatePass.coupon);
    const isFree = candidatePass.coupon?.audience_policies[0]?.form === 'free';

    for (const d of datesOfMonth) {
      const avRaw = candidatePass.availability?.[d];
      // 'unavailable' treated same as 'booked' for coloring purposes.
      const status: 'available' | 'booked' | 'closed' | 'none' =
        avRaw === 'available' ? 'available' :
        avRaw === 'booked' || avRaw === 'unavailable' ? 'booked' :
        avRaw === 'closed' ? 'closed' : 'none';
      // Show the coupon label on available days; blank on booked/closed/none.
      const bestLabel = status === 'available' ? summary : '';
      out[d] = { best: bestLabel, isFree: status === 'available' && isFree, status };
    }
    return out;
  }, [datesOfMonth, slug, engineUser]);

  if (!slug) return <div className="max-w-3xl mx-auto p-4">Missing slug.</div>;
  if (!attraction) return <div className="max-w-3xl mx-auto p-4">Attraction "{slug}" not found.</div>;

  const addressCity = attraction.address?.city ?? '';
  const addressState = attraction.address?.state ?? '';
  const town = addressCity && addressState ? `${addressCity}, ${addressState}` : (addressCity || '');

  const isTimedEntry = attraction.reservation?.required === 'timed_entry';

  return (
    <div className="max-w-3xl mx-auto" style={{ background: 'var(--white)', minHeight: '100vh' }}>
      <HeroBanner
        imageSrc={heroImg}
        museumName={attraction.name}
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
          variant="detail"
        />
      </section>

      <DescriptionBlock description={attraction.description ?? null} />

      {/* Coupon / perks section */}
      <section style={{ padding: 14, background: 'var(--g-pale)', borderBottom: '1px solid var(--rule)' }}>
        <h3 style={{
          margin: '0 0 8px', fontSize: 13, fontWeight: 600,
          color: 'var(--g)', textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>Your perks · what it'll cost you</h3>

        {/* Two-step guide for timed-entry attractions */}
        {isTimedEntry && (
          <div
            style={{
              background: 'var(--white)',
              border: '1px solid var(--g)',
              borderRadius: 8,
              padding: '10px 14px',
              marginBottom: 12,
              fontSize: 13,
              color: 'var(--ink-2)',
            }}
            data-testid="timed-entry-guide"
          >
            <div style={{ fontWeight: 600, color: 'var(--g)', marginBottom: 4, fontSize: 12 }}>
              预订流程（限时入场景点）
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>
                <span style={{ color: 'var(--g)', fontWeight: 700 }}>①</span>{' '}
                从图书馆领码／取 pass
              </div>
              <div>
                <span style={{ color: 'var(--g)', fontWeight: 700 }}>②</span>{' '}
                去景点官网用码订时段
                {attraction.reservation?.booking_url && (
                  <>
                    {' · '}
                    <a
                      href={attraction.reservation.booking_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--g)', fontWeight: 600, textDecoration: 'none' }}
                    >
                      预约 →
                    </a>
                  </>
                )}
                {attraction.reservation?.pass_holder_url && (
                  <>
                    {' '}
                    <a
                      href={attraction.reservation.pass_holder_url ?? undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--g-2)', fontWeight: 500, fontSize: 11, textDecoration: 'none' }}
                    >
                      (持卡人专页 →)
                    </a>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

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
          {selectedDayRecs.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No coupons available on this date
            </div>
          ) : (
            selectedDayRecs.map((rec, i) => {
              const lib = getLibrary(rec.pass.library_id);
              if (!lib) return null;
              if (!authUser) {
                return (
                  <GuestLockedRow
                    key={`${rec.pass.library_id}-${i}`}
                    pass={rec.pass}
                    library={lib}
                    onSignInRequest={() => setSignInOpen(true)}
                  />
                );
              }
              const distanceMi = userGeo && lib.geo ? haversineMiles(userGeo, lib.geo) : null;
              return (
                <CouponRow
                  key={`${rec.pass.library_id}-${i}`}
                  pass={rec.pass}
                  library={lib}
                  verdict={rec.verdict}
                  distanceMi={distanceMi}
                  showTopBorder={i > 0}
                  onBook={setBookingPass}
                />
              );
            })
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
