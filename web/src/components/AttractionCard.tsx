import { Link } from 'react-router';
import type { Attraction } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { FavoriteButton } from './FavoriteButton';
import { applyDiscount } from '../lib/price-fallback';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  isGuestOrEmpty?: boolean;
  sourceCountForGuest?: number;
  /** True if the attraction itself isn't operating today (museum holiday, weekly closure).
   *  Distinct from "no library passes available" — that's just sold out. */
  closedToday?: boolean;
}

/** Pass-type display metadata. Icons chosen by essence:
 *   - digital: 📱 instant, no pickup, on your phone
 *   - physical-coupon: 🎟 paper ticket you collect at the library
 *   - loan-card: 🔄 a card you borrow then return
 */
const TYPE_META = {
  'digital':         { icon: '📱', word: 'Digital',         fg: 'var(--g)'  },
  'physical-coupon': { icon: '🎟', word: 'Pickup',          fg: 'var(--au)' },
  'loan-card':       { icon: '🔄', word: 'Pickup & return', fg: 'var(--or)' },
  'unknown':         { icon: '·',  word: 'Pass',            fg: 'var(--ink-3)' },
} as const;

// Discount-class ranking (lower = better) for deciding "clear winner"
const DISCOUNT_RANK: Record<string, number> = {
  free: 0, half: 1, 'percent-off': 2, 'dollar-off': 3, price: 4, discount: 5, unknown: 99,
};

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

/** A "clear winner" exists iff the top option has a strictly better discount class
 *  than the second. Ties (e.g. two Free digital passes) get no badge. */
function hasClearWinner(tags: PickedTag[]): boolean {
  if (tags.length < 2) return tags.length === 1;
  const r0 = DISCOUNT_RANK[tags[0].pass.discount.class] ?? 99;
  const r1 = DISCOUNT_RANK[tags[1].pass.discount.class] ?? 99;
  return r0 < r1;
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
  closedToday = false,
}: Props) {
  const town = townFromAddress(attraction.address);
  const adult = attraction.original_price?.adult ?? null;
  const child = attraction.original_price?.child ?? null;
  const total = pickedTags.length;
  const showWinnerBadge = !closedToday && !isGuestOrEmpty && hasClearWinner(pickedTags);

  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

  return (
    <Link
      to={`/attractions/${attraction.slug}`}
      className="block rounded-lg overflow-hidden mb-3 transition-colors active:bg-[color:var(--paper)]"
      style={{
        background: 'var(--white)',
        color: 'inherit',
        textDecoration: 'none',
        border: '1px solid var(--rule)',
      }}
    >
      {/* Header: image + basic info */}
      <div className="flex gap-3 p-3" style={dim}>
        <div className="relative flex-shrink-0">
          <img
            src={heroSrc(attraction)}
            alt=""
            loading="lazy"
            className="rounded-md object-cover bg-[color:var(--paper)]"
            style={{ width: 110, height: 110 }}
          />
          <div className="absolute" style={{ top: -6, right: -6 }}>
            <FavoriteButton slug={attraction.slug} variant="overlay" />
          </div>
        </div>

        <div className="flex-grow min-w-0">
          <h3 className="font-serif" style={{
            fontSize: 16, lineHeight: 1.25, color: 'var(--ink-2)', fontWeight: 700,
          }}>
            {attraction.museum_name}
          </h3>

          {town && (
            <p className="mt-1" style={{ fontSize: 12, color: 'var(--ink-3)' }}>📍 {town}</p>
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

          {adult != null && (
            <p className="mt-2" style={{ fontSize: 13, color: 'var(--ink-2)' }}>
              <span style={{ color: 'var(--ink-3)', fontSize: 11 }}>From </span>
              <span style={{ fontWeight: 600 }}>{fmtMoney(adult)}</span>
              <span style={{ color: 'var(--ink-3)', fontSize: 11 }}> / adult</span>
              {child != null && child !== adult && (
                <span style={{ color: 'var(--ink-3)', fontSize: 11 }}>
                  {' · '}{fmtMoney(child)} / child
                </span>
              )}
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

      {/* Body: list of pass options, or empty / guest state */}
      {closedToday ? null : isGuestOrEmpty ? (
        <div className="px-3 pb-3" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
          <span aria-hidden>🔒</span> Sign in to view <b>{sourceCountForGuest}</b> discount option{sourceCountForGuest === 1 ? '' : 's'}
        </div>
      ) : total === 0 ? (
        <div className="px-3 pb-3" style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
          No passes available on this date.
        </div>
      ) : (
        <div className="border-t" style={{ borderColor: 'var(--rule)' }}>
          {pickedTags.slice(0, MAX_ROWS_VISIBLE).map((t, i) => {
            const meta = TYPE_META[t.pass.pass_type];
            const finalPrice = applyDiscount(attraction.original_price, t.pass.discount);
            const showStrike = adult != null && finalPrice != null && finalPrice !== adult;
            const isDigital = t.pass.pass_type === 'digital';
            const isWinner = i === 0 && showWinnerBadge;

            return (
              <div
                key={`${t.pass.library_id}-${i}`}
                className="flex items-center gap-3 px-3 py-2.5"
                style={{
                  borderTop: i === 0 ? 'none' : '1px solid var(--rule)',
                  background: isWinner ? 'var(--g-pale)' : 'transparent',
                }}
              >
                <span aria-hidden style={{
                  width: 28, height: 28, borderRadius: 14,
                  background: meta.fg, color: 'var(--white)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, flexShrink: 0,
                }}>{meta.icon}</span>

                <div className="flex-grow min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-2)' }}>
                      {isDigital ? t.library.name : t.library.town}
                    </span>
                    {!isDigital && t.distanceMi != null && (
                      <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                        · {Math.round(t.distanceMi)} mi
                      </span>
                    )}
                    {isWinner && (
                      <span className="ml-1 px-1.5 py-0.5 rounded-sm" style={{
                        fontSize: 10, fontWeight: 600,
                        background: 'var(--g)', color: 'var(--white)',
                        letterSpacing: '0.04em',
                      }}>
                        BEST OFFER
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                    {meta.word} · {t.pass.discount.label || t.pass.discount.class}
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  {showStrike ? (
                    <>
                      <div style={{ fontSize: 11, color: 'var(--ink-3)', textDecoration: 'line-through', lineHeight: 1 }}>
                        {fmtMoney(adult)}
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: meta.fg, lineHeight: 1.2 }}>
                        {finalPrice === 0 ? 'Free' : fmtMoney(finalPrice)}
                      </div>
                    </>
                  ) : finalPrice === 0 ? (
                    <div style={{ fontSize: 15, fontWeight: 700, color: meta.fg }}>Free</div>
                  ) : (
                    <div style={{ fontSize: 12, fontWeight: 500, color: meta.fg }}>
                      {t.pass.discount.label || '—'}
                    </div>
                  )}
                </div>
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
