import type { Attraction, Address } from '../data/types';
import { MuseumReservationBanner } from './MuseumReservationBanner';
import { hoursDisplay } from '../lib/hours';
import { PinIcon, ClockIcon, TicketIcon } from './icons';

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '';
  if (v === 0) return 'FREE';
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}

/** Extract "City, MA" from a structured Address object. */
function townFromAddr(addr: Address | null | undefined): string {
  if (!addr?.city) return '';
  const state = addr.state ?? 'MA';
  return `${addr.city}, ${state}`;
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
  const town = townFromAddr(attraction.address);

  // Build a Map<audience, price> taking FIRST occurrence only.
  // First occurrence = standard/rack price; subsequent entries may be
  // discounted (e.g. EBT rate) which we don't want to show as the headline.
  const TIER_ORDER = ['adult', 'senior', 'youth', 'child', 'student', 'educator', 'military'];
  const priceMap = new Map<string, number | null>();
  for (const ap of (attraction.prices ?? [])) {
    if (!priceMap.has(ap.audience)) {
      priceMap.set(ap.audience, ap.price);
    }
  }

  const adultPrice = priceMap.get('adult') ?? null;

  // Build display tiers: always include adult when present; include other tiers
  // only when they differ from the adult price (same-price tiers are noise).
  const tiers: Array<{ label: string; value: number | null }> = [];
  for (const aud of TIER_ORDER) {
    if (!priceMap.has(aud)) continue;
    const price = priceMap.get(aud) ?? null;
    if (price == null) continue;  // skip null-price entries
    if (aud === 'adult') {
      tiers.push({ label: 'adult', value: price });
    } else if (price !== adultPrice) {
      tiers.push({ label: aud, value: price });
    }
  }

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

      {tiers.length > 0 && (() => {
        // Flatten everything into a single token stream — one gap rule for all
        // spaces, no nested flex wrappers, no double gaps.
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
        return (
          <p className="info-line" style={{ color: 'var(--ink-3)' }}>
            <span className="info-icon"><TicketIcon /></span>
            <span className="price-tokens">{tokens}</span>
          </p>
        );
      })()}

      <MuseumReservationBanner
        reservation={attraction.reservation}
        attractionName={attraction.name}
        variant={variant}
      />
    </>
  );
}
