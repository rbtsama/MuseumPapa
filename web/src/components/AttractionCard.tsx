import { Link } from 'react-router';
import type { Attraction, Pass } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { FavoriteButton } from './FavoriteButton';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine, formatCapacity } from './CouponLine';
import { MuseumReservationBanner } from './MuseumReservationBanner';
import { hoursDisplay } from '../lib/hours';
import { heroSrc } from '../lib/hero';
import { getBranchesForPass } from '../data/load';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  isGuestOrEmpty?: boolean;
  sourceCountForGuest?: number;
  closedToday?: boolean;
  /** Selected date (ISO) — used to look up today's hours. */
  date?: string;
  /** Called when user taps a per-pass "Book" button. List page opens the modal. */
  onBookPass?: (pass: Pass) => void;
}

const MAX_ROWS_VISIBLE = 4;

function PersonIcon() {
  return (
    <svg width="10" height="10" viewBox="4 0 16 24" fill="currentColor" aria-hidden
      style={{ display: 'inline-block', verticalAlign: '-1px' }}>
      <path d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0zM3.75 20.1a8.25 8.25 0 0 1 16.5 0 .75.75 0 0 1-.44.69 18.7 18.7 0 0 1-7.81 1.7c-2.79 0-5.43-.6-7.81-1.7a.75.75 0 0 1-.44-.69z" />
    </svg>
  );
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '';
  if (v === 0) return 'Free';
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}

function townFromAddress(addr: string): string {
  const m = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\s+\d{5}/);
  if (m) return `${m[1].trim()}, MA`;
  const m2 = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\b/);
  return m2 ? `${m2[1].trim()}, MA` : '';
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
  closedToday = false, date, onBookPass,
}: Props) {
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
  const total = pickedTags.length;

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
    const lbl = freeUnder != null ? `age ${freeUnder}+` : 'kids';
    tiers.push({ label: lbl, value: childPrice });
  }
  if (studentPrice != null && studentPrice !== adultPrice) tiers.push({ label: 'student', value: studentPrice });
  if (educatorPrice != null && educatorPrice !== adultPrice) tiers.push({ label: 'educator', value: educatorPrice });
  if (militaryPrice != null && militaryPrice !== adultPrice) tiers.push({ label: 'military', value: militaryPrice });
  const hoursInfo = date ? hoursDisplay(attraction, date) : null;

  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

  const handleBook = (e: React.SyntheticEvent, pass: Pass) => {
    e.preventDefault();
    e.stopPropagation();
    onBookPass?.(pass);
  };

  const handleBookKeyDown = (e: React.KeyboardEvent, pass: Pass) => {
    if (e.key === 'Enter' || e.key === ' ') {
      handleBook(e, pass);
    }
  };

  return (
    <Link
      to={`/attractions/${attraction.slug}`}
      className="block rounded-lg overflow-hidden mb-3 transition-colors active:bg-[color:var(--paper)]"
      style={{
        position: 'relative',
        background: 'var(--white)',
        color: 'inherit',
        textDecoration: 'none',
        border: '1px solid var(--rule)',
      }}
    >
      <div className="absolute" style={{ top: 6, right: 6, zIndex: 1 }}>
        <FavoriteButton slug={attraction.slug} variant="overlay" />
      </div>

      {/* Header: image + basic info */}
      <div className="flex gap-3 p-3" style={dim}>
        <img
          src={heroSrc(attraction)}
          alt=""
          loading="lazy"
          className="rounded-md object-cover bg-[color:var(--paper)] flex-shrink-0"
          style={{ width: 110, height: 110 }}
        />

        <div className="flex-grow min-w-0 pr-9">
          <h3 className="font-serif" style={{
            fontSize: 16, lineHeight: 1.25, color: 'var(--ink-2)', fontWeight: 700,
          }}>
            {attraction.museum_name}
          </h3>

          {town && (
            <p className="mt-1" style={{ fontSize: 12, color: 'var(--ink-3)' }}>📍 {town}</p>
          )}

          {hoursInfo && !closedToday && (
            <p className="mt-0.5" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
              🕘 {hoursInfo.varies ? <span style={{ color: 'var(--ink-2)' }}>{hoursInfo.value}</span> : <>Open today · <span style={{ color: 'var(--ink-2)' }}>{hoursInfo.value}</span></>}
            </p>
          )}

          {attraction.categories.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {attraction.categories.slice(0, 3).map(c => (
                <span key={c} className="px-1.5 py-0.5 rounded"
                  style={{ fontSize: 11, background: 'var(--paper)', color: 'var(--ink-3)' }}>
                  {c}
                </span>
              ))}
            </div>
          )}

          {(tiers.length > 0 || freeUnder != null) && (
            <p className="mt-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5" style={{ fontSize: 12 }}>
              {tiers.map((t, i) => (
                <span key={`${t.label}-${i}`} className="inline-flex items-baseline gap-1">
                  {i > 0 && <span style={{ color: 'var(--ink-3)' }}>·</span>}
                  {tiers.length > 1 && (
                    <span style={{ color: 'var(--ink-3)' }}>{t.label}</span>
                  )}
                  <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--ink-2)' }}>
                    {fmtMoney(t.value)}
                  </span>
                </span>
              ))}
              {freeUnder != null && (
                <span className="inline-flex items-baseline gap-1">
                  {tiers.length > 0 && <span style={{ color: 'var(--ink-3)' }}>·</span>}
                  <span style={{ color: 'var(--ink-3)' }}>age &lt;{freeUnder}</span>
                  <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--ink-2)' }}>FREE</span>
                </span>
              )}
            </p>
          )}

          {closedToday && (
            <span className="inline-block mt-2 px-2 py-0.5 rounded-md" style={{
              fontSize: 11, fontWeight: 500,
              background: 'var(--rd-pale)', color: 'var(--rd)',
            }}>
              Closed
            </span>
          )}
        </div>
      </div>

      {/* Body: pass options, or empty / guest state */}
      {closedToday ? null : (
        <div className="border-t" style={{ borderColor: 'var(--rule)' }}>
          {isGuestOrEmpty ? (
            <div className="px-3 py-3" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              Sign in to view <b>{sourceCountForGuest}</b> discount option{sourceCountForGuest === 1 ? '' : 's'}
            </div>
          ) : total === 0 ? (
            <div className="px-3 py-3 text-center" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
              No coupons available on this date
            </div>
          ) : (
            <>
              {attraction.museum_reservation && (
                <MuseumReservationBanner
                  reservation={attraction.museum_reservation}
                  attractionName={attraction.museum_name}
                  variant="card"
                />
              )}
          {pickedTags.slice(0, MAX_ROWS_VISIBLE).map((t, i) => {
            const isDigital = t.pass.pickup_method === 'digital';
            // For physical, prefer the actual pickup branch(es). Single-branch
            // libs synthesize `<lib_id>--main`, so this still resolves cleanly.
            const branches = isDigital ? [] : getBranchesForPass(t.pass);
            const showBranchLabel =
              !isDigital && branches.length === 1 && branches[0].id !== `${t.pass.library_id}--main`;
            const branchSummary = !isDigital && branches.length > 1
              ? `${t.library.town} · ${branches.length} branches`
              : null;

            const locationText = isDigital ? t.library.name
              : branchSummary ? branchSummary
              : showBranchLabel ? `${branches[0].name} · ${branches[0].address.street}`
              : t.library.town;

            const capacityText = formatCapacity(t.pass.coupon.capacity);

            return (
              <div
                key={`${t.pass.library_id}-${i}`}
                className="flex items-center gap-3 px-3 py-2"
                style={{ borderTop: i === 0 ? 'none' : '1px solid var(--rule)' }}
              >
                <div className="flex-grow min-w-0 flex flex-col gap-0.5">
                  <div className="flex items-center gap-1.5 min-w-0" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
                    <span style={{ color: 'var(--ink-2)', fontWeight: 500, fontSize: 13,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {locationText}
                    </span>
                    {!isDigital && t.distanceMi != null && (
                      <span className="flex-shrink-0" style={{ fontSize: 11 }}>
                        · {Math.round(t.distanceMi)} mi
                      </span>
                    )}
                    <span className="flex-shrink-0" style={{ fontSize: 11 }}>·</span>
                    <span className="flex-shrink-0">
                      <PassTypeLabel type={t.pass.pass_type} />
                    </span>
                  </div>
                  <div className="flex items-baseline flex-wrap gap-x-1.5 gap-y-0.5 min-w-0">
                    {capacityText && (
                      <>
                        <span className="inline-flex items-center gap-1"
                          style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                          <PersonIcon /> {capacityText.toLowerCase()}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>·</span>
                      </>
                    )}
                    <CouponLine coupon={t.pass.coupon} align="left" />
                  </div>
                </div>

                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleBook(e, t.pass)}
                  onKeyDown={(e) => handleBookKeyDown(e, t.pass)}
                  className="flex-shrink-0 rounded-md inline-block"
                  style={{
                    background: 'var(--g)',
                    color: 'var(--white)',
                    fontSize: 12,
                    fontWeight: 600,
                    padding: '6px 12px',
                    border: 'none',
                    cursor: 'pointer',
                    userSelect: 'none',
                  }}
                >
                  Book
                </span>
              </div>
            );
          })}

          {total > MAX_ROWS_VISIBLE && (
            <div className="px-3 py-2 text-center" style={{
              borderTop: '1px solid var(--rule)', background: 'var(--bg)',
              fontSize: 12, color: 'var(--g)', fontWeight: 500,
            }}>
              + {total - MAX_ROWS_VISIBLE} more option{total - MAX_ROWS_VISIBLE === 1 ? '' : 's'} →
            </div>
          )}
            </>
          )}
        </div>
      )}
    </Link>
  );
}
