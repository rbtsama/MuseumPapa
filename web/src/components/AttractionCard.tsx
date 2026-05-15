import { Link } from 'react-router';
import type { Attraction } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { FavoriteButton } from './FavoriteButton';
import { PassTypeLabel } from './PassTypeLabel';
import { applyDiscount } from '../lib/price-fallback';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  isGuestOrEmpty?: boolean;
  sourceCountForGuest?: number;
  closedToday?: boolean;
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
  closedToday = false,
}: Props) {
  const town = townFromAddress(attraction.address);
  const adult = attraction.original_price?.adult ?? null;
  const child = attraction.original_price?.child ?? null;
  const total = pickedTags.length;

  const dim = closedToday ? { filter: 'grayscale(0.7)', opacity: 0.55 } : {};

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
      {/* Favorite — top-right of the CARD (per Booking.com/Airbnb mobile pattern, but
          attached to the card frame rather than the image so it doesn't overlap the photo) */}
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
          {/* pr-9 reserves space for the favorite button overlay */}
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
            <p className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5" style={{ fontSize: 12 }}>
              <span style={{ color: 'var(--ink-3)' }}>Adult</span>
              <span style={{ fontWeight: 700, fontSize: 14,
                color: adult === 0 ? 'var(--g)' : 'var(--ink-2)' }}>
                {fmtMoney(adult)}
              </span>
              {child != null && (
                <>
                  <span className="ml-1" style={{ color: 'var(--ink-3)' }}>Child</span>
                  <span style={{ fontWeight: 700, fontSize: 14,
                    color: child === 0 ? 'var(--g)' : 'var(--ink-2)' }}>
                    {fmtMoney(child)}
                  </span>
                </>
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
            const finalPrice = applyDiscount(attraction.original_price, t.pass.discount);
            const showStrike = adult != null && finalPrice != null && finalPrice !== adult;
            const isDigital = t.pass.pass_type === 'digital';

            return (
              <div
                key={`${t.pass.library_id}-${i}`}
                className="flex items-center gap-2.5 px-3 py-2"
                style={{
                  borderTop: i === 0 ? 'none' : '1px solid var(--rule)',
                }}
              >
                <PassTypeLabel type={t.pass.pass_type} />

                <div className="flex-grow min-w-0">
                  <div style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {isDigital ? t.library.name : t.library.town}
                    {!isDigital && t.distanceMi != null && (
                      <span style={{ fontSize: 11, color: 'var(--ink-3)', fontWeight: 400 }}>
                        {' '}· {Math.round(t.distanceMi)} mi
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  {showStrike ? (
                    <div className="flex items-baseline gap-1.5">
                      <span style={{ fontSize: 11, color: 'var(--ink-3)', textDecoration: 'line-through' }}>
                        {fmtMoney(adult)}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink-2)' }}>
                        {finalPrice === 0 ? 'Free' : fmtMoney(finalPrice)}
                      </span>
                    </div>
                  ) : finalPrice === 0 ? (
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--g)' }}>Free</span>
                  ) : (
                    <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--ink-2)' }}>
                      {t.pass.discount.label || '—'}
                    </span>
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
