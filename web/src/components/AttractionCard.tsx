import { Link } from 'react-router';
import type { Attraction, Pass } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { FavoriteButton } from './FavoriteButton';
import { PassTypeLabel } from './PassTypeLabel';
import { CouponLine } from './CouponLine';
import { hoursDisplay } from '../lib/hours';
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

function heroSrc(a: Attraction): string {
  if (a.hero_image?.local_path) {
    const filename = a.hero_image.local_path.split(/[\\/]/).pop() ?? '';
    if (filename) return `/images/${filename}`;
  }
  const cat = a.categories?.[0]?.toLowerCase() ?? 'default';
  const known = ['family','children','history','nature','art','science','ocean','recreation'];
  return `/placeholders/${known.includes(cat) ? cat : 'default'}.svg`;
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
  const total = pickedTags.length;

  // Up to 4 known tiers, in display priority order. "adult" is shown without label.
  const tiers: Array<{ label: string | null; value: number }> = [];
  if (adultPrice != null) tiers.push({ label: 'adult', value: adultPrice });
  if (youthPrice != null) tiers.push({ label: 'youth', value: youthPrice });
  if (childPrice != null) tiers.push({ label: 'kids', value: childPrice });
  if (seniorPrice != null && tiers.length < 4) tiers.push({ label: 'senior', value: seniorPrice });
  if (studentPrice != null && tiers.length < 4) tiers.push({ label: 'student', value: studentPrice });
  const hoursInfo = date ? hoursDisplay(attraction, date) : null;

  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

  const handleBook = (e: React.MouseEvent, pass: Pass) => {
    e.preventDefault();
    e.stopPropagation();
    onBookPass?.(pass);
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
                  style={{ fontSize: 10, background: 'var(--paper)', color: 'var(--ink-3)' }}>
                  {c}
                </span>
              ))}
            </div>
          )}

          {/* Multi-tier admission price line — surface up to 4 known tiers
              (adult / youth / kids / senior or student). Calm bold black; the
              real-money attention belongs on the discounted option rows below. */}
          {tiers.length > 0 && (
            <p className="mt-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5" style={{ fontSize: 12 }}>
              {tiers.slice(0, 4).map((t, i) => (
                <span key={`${t.label}-${i}`} className="inline-flex items-baseline gap-1">
                  {i > 0 && <span style={{ color: 'var(--ink-3)' }}>·</span>}
                  <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--ink-2)' }}>
                    {fmtMoney(t.value)}
                  </span>
                  {t.label && tiers.length > 1 && (
                    <span style={{ color: 'var(--ink-3)' }}>{t.label}</span>
                  )}
                </span>
              ))}
            </p>
          )}

          {closedToday && (
            <span className="inline-block mt-2 px-2 py-0.5 rounded-md" style={{
              fontSize: 11, fontWeight: 500,
              background: 'var(--rd-pale)', color: 'var(--rd)',
            }}>
              Closed today
            </span>
          )}
        </div>
      </div>

      {/* Body: pass options, or empty / guest state */}
      {closedToday ? null : isGuestOrEmpty ? (
        <div className="px-3 pb-3" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
          Sign in to view <b>{sourceCountForGuest}</b> discount option{sourceCountForGuest === 1 ? '' : 's'}
        </div>
      ) : total === 0 ? (
        <div className="px-3 pb-3 text-center" style={{ fontSize: 11, color: 'var(--ink-3)', fontStyle: 'italic' }}>
          No coupons available today
        </div>
      ) : (
        <div className="border-t" style={{ borderColor: 'var(--rule)' }}>
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

            return (
              <div
                key={`${t.pass.library_id}-${i}`}
                className="flex items-center gap-2 px-3 py-2.5"
                style={{ borderTop: i === 0 ? 'none' : '1px solid var(--rule)' }}
              >
                <PassTypeLabel type={t.pass.pass_type} />

                <div className="flex-grow min-w-0">
                  <div style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {isDigital ? t.library.name
                      : branchSummary ? branchSummary
                      : showBranchLabel ? `${branches[0].name} · ${branches[0].address.street}`
                      : t.library.town}
                    {!isDigital && t.distanceMi != null && (
                      <span style={{ fontSize: 11, color: 'var(--ink-3)', fontWeight: 400 }}>
                        {' '}· {Math.round(t.distanceMi)} mi
                      </span>
                    )}
                  </div>
                </div>

                <CouponLine coupon={t.pass.coupon} />

                <button
                  type="button"
                  onClick={(e) => handleBook(e, t.pass)}
                  className="flex-shrink-0 rounded-md"
                  style={{
                    background: 'var(--g)',
                    color: 'var(--white)',
                    fontSize: 12,
                    fontWeight: 600,
                    padding: '6px 12px',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  Book
                </button>
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
        </div>
      )}
    </Link>
  );
}
