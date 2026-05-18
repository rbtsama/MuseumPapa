import type { Attraction } from '../data/types';
import { MuseumReservationBanner } from './MuseumReservationBanner';
import { hoursDisplay } from '../lib/hours';
import { townFromAddress } from '../lib/address';
import { PinIcon, ClockIcon, TicketIcon } from './icons';

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '';
  if (v === 0) return 'FREE';
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}


interface AttractionInfoRowsProps {
  attraction: Attraction;
  /** ISO date — used for today's hours lookup. Falls back to no hours row when undefined. */
  date?: string;
  /** True when the attraction is closed on `date`. Hides the hours row entirely
   *  (mirrors AttractionCard which doesn't render hours when closedToday). */
  closedToday?: boolean;
  /** 'card' (default) renders the reservation row as plain text — the list
   *  card is itself a clickable <Link> tile, so a nested anchor would be
   *  invalid DOM. 'detail' adds the inline Reserve → link to the reservation
   *  row so the user can jump straight to the museum's booking page. */
  variant?: 'card' | 'detail';
}

/**
 * The 4 meta rows shared between the list-page card and the detail page:
 *   📍 town · 🕘 hours · 🎫 price · ⚠ reservation
 *
 * Single source of truth: same computation, same render, same icons, so the
 * list and detail page never disagree on what a given attraction costs.
 */
export function AttractionInfoRows({
  attraction, date, closedToday = false, variant = 'card',
}: AttractionInfoRowsProps) {
  const town = townFromAddress(attraction.address);
  const op = attraction.original_price;
  const adultPrice = op?.age_pricing?.adult?.price ?? null;
  const youthPrice = op?.age_pricing?.youth?.price ?? null;
  const childPrice = op?.age_pricing?.child?.price ?? null;
  const seniorPrice = op?.age_pricing?.senior?.price ?? null;
  const studentPrice = op?.identity_pricing?.student?.price ?? null;
  const educatorPrice = op?.identity_pricing?.educator?.price ?? null;
  const militaryPrice = op?.identity_pricing?.military?.price ?? null;
  const freeUnder = op?.age_pricing?.free_under_age ?? null;

  // Price tiers — list each only when it differs from the adult price. Same-
  // price tiers are noise (Boston Children's Museum has Adult=Child=$24 → just
  // show Adult). When free_under_age is set AND child has its own price, label
  // the child tier with its lower bound so the gap reads cleanly:
  //   $26 adult · $21 senior · $18 age 5+ · FREE age <5
  // Identity tiers (student/educator/military) inline alongside age tiers, no
  // "Waivers" wrapper.
  const tiers: Array<{ label: string; value: number }> = [];
  if (adultPrice != null) tiers.push({ label: 'adult', value: adultPrice });
  if (seniorPrice != null && seniorPrice !== adultPrice) tiers.push({ label: 'senior', value: seniorPrice });
  if (youthPrice != null && youthPrice !== adultPrice) tiers.push({ label: 'youth', value: youthPrice });
  if (childPrice != null && childPrice !== adultPrice) {
    const lbl = freeUnder != null ? `age ${freeUnder}+` : 'child';
    tiers.push({ label: lbl, value: childPrice });
  }
  if (studentPrice != null && studentPrice !== adultPrice) tiers.push({ label: 'student', value: studentPrice });
  if (educatorPrice != null && educatorPrice !== adultPrice) tiers.push({ label: 'educator', value: educatorPrice });
  if (militaryPrice != null && militaryPrice !== adultPrice) tiers.push({ label: 'military', value: militaryPrice });

  const hoursInfo = date ? hoursDisplay(attraction, date) : null;

  return (
    <>
      {town && (
        <p className="info-line" style={{ color: 'var(--ink-3)' }}>
          <span className="info-icon"><PinIcon /></span>
          <span>{town}</span>
        </p>
      )}

      {hoursInfo && !closedToday && (
        <p className="info-line" style={{ color: 'var(--ink-3)' }}>
          <span className="info-icon"><ClockIcon /></span>
          <span>
            {hoursInfo.varies
              ? <span style={{ color: 'var(--ink-2)' }}>{hoursInfo.value}</span>
              : <>Open <span style={{ color: 'var(--ink-2)' }}>{hoursInfo.value}</span></>}
          </span>
        </p>
      )}

      {(tiers.length > 0 || freeUnder != null) && (() => {
        // Flatten everything into a single token stream so one gap rule
        // controls every space — no nested flex wrappers, no double gaps,
        // no leading space before "age <N FREE".
        const tokens: React.ReactNode[] = [];
        tiers.forEach((t, i) => {
          if (i > 0) tokens.push(<span key={`sep-${i}`} aria-hidden>·</span>);
          if (tiers.length > 1) tokens.push(<span key={`lbl-${i}`}>{t.label}</span>);
          tokens.push(
            <span key={`val-${i}`} style={{ fontWeight: 700, color: 'var(--ink-2)' }}>
              {fmtMoney(t.value)}
            </span>
          );
        });
        if (freeUnder != null) {
          if (tiers.length > 0) tokens.push(<span key="fu-sep" aria-hidden>·</span>);
          tokens.push(<span key="fu-lbl">{`age <${freeUnder}`}</span>);
          tokens.push(
            <span key="fu-val" style={{ fontWeight: 700, color: 'var(--ink-2)' }}>FREE</span>
          );
        }
        return (
          <p className="info-line" style={{ color: 'var(--ink-3)' }}>
            <span className="info-icon"><TicketIcon /></span>
            <span className="price-tokens">{tokens}</span>
          </p>
        );
      })()}

      <MuseumReservationBanner
        reservation={attraction.museum_reservation}
        attractionName={attraction.museum_name}
        variant={variant}
      />
    </>
  );
}
