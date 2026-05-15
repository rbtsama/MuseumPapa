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
}

const TYPE_META = {
  'digital':         { icon: '⚡', word: 'digital',  fg: 'var(--g)'  },
  'physical-coupon': { icon: '🎫', word: 'pickup',   fg: 'var(--au)' },
  'loan-card':       { icon: '🔁', word: 'loan',     fg: 'var(--or)' },
  'unknown':         { icon: '·',  word: 'pass',     fg: 'var(--ink-3)' },
} as const;

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

function summarizePassTypes(tags: PickedTag[]) {
  const buckets = { digital: 0, 'physical-coupon': 0, 'loan-card': 0 };
  for (const t of tags) {
    if (t.pass.pass_type in buckets) {
      buckets[t.pass.pass_type as keyof typeof buckets] += 1;
    }
  }
  return buckets;
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
}: Props) {
  const town = townFromAddress(attraction.address);
  const adult = attraction.original_price?.adult ?? null;
  const child = attraction.original_price?.child ?? null;
  const totalDiscounts = pickedTags.length;
  const best = pickedTags[0] ?? null;
  const bestFinal = best ? applyDiscount(attraction.original_price, best.pass.discount) : null;
  const bestMeta = best ? TYPE_META[best.pass.pass_type] : null;
  const bucket = summarizePassTypes(pickedTags);

  return (
    <Link
      to={`/attractions/${attraction.slug}`}
      className="block bg-[color:var(--white)] rounded-lg overflow-hidden mb-3 transition-colors active:bg-[color:var(--paper)]"
      style={{
        color: 'inherit',
        textDecoration: 'none',
        border: '1px solid var(--rule)',
      }}
    >
      {/* Header: image + basic info */}
      <div className="flex gap-3 p-3">
        <div className="relative flex-shrink-0">
          <img
            src={heroSrc(attraction)}
            alt=""
            loading="lazy"
            className="rounded-md object-cover bg-[color:var(--paper)]"
            style={{ width: 110, height: 110 }}
          />
          {!isGuestOrEmpty && totalDiscounts > 0 && (
            <div className="absolute bottom-1 left-1 flex items-center gap-1 px-1.5 py-0.5 rounded"
              style={{ background: 'var(--white)', fontSize: 10, fontWeight: 500, color: 'var(--g)' }}>
              <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--g)' }} />
              Available
            </div>
          )}
        </div>

        <div className="flex-grow min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-serif" style={{
              fontSize: 16, lineHeight: 1.25, color: 'var(--ink-2)', fontWeight: 700,
            }}>
              {attraction.museum_name}
            </h3>
            <div className="flex-shrink-0 -mt-1 -mr-1">
              <FavoriteButton slug={attraction.slug} size={20} />
            </div>
          </div>

          {town && (
            <p className="mt-1" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              📍 {town}
            </p>
          )}

          {attraction.categories.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {attraction.categories.slice(0, 3).map(c => (
                <span key={c} className="px-1.5 py-0.5 rounded"
                  style={{
                    fontSize: 10,
                    background: 'var(--paper)',
                    color: 'var(--ink-3)',
                  }}>
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
        </div>
      </div>

      {/* Best deal highlight (like TripAdvisor's quote box) */}
      {isGuestOrEmpty ? (
        <div className="mx-3 mb-3 rounded-md p-2.5"
          style={{ background: 'var(--g-pale)', border: '1px solid var(--g-light)' }}>
          <p style={{ fontSize: 12, color: 'var(--ink-2)' }}>
            <span aria-hidden>💡</span>{' '}
            Sign in to view <b>{sourceCountForGuest}</b> discount option{sourceCountForGuest === 1 ? '' : 's'}
          </p>
        </div>
      ) : totalDiscounts === 0 ? (
        <div className="mx-3 mb-3 rounded-md p-2.5"
          style={{ background: 'var(--paper)' }}>
          <p style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
            No passes available on this date.
          </p>
        </div>
      ) : (
        <div className="mx-3 mb-3 rounded-md p-2.5"
          style={{ background: 'var(--g-pale)', border: '1px solid var(--g-light)' }}>
          <div className="flex items-start gap-2">
            <span aria-hidden style={{ fontSize: 16, lineHeight: 1 }}>{bestMeta!.icon}</span>
            <div className="flex-grow min-w-0">
              <div style={{ fontSize: 11, color: 'var(--g-2)', fontWeight: 500, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Best deal today
              </div>
              <div className="mt-0.5" style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500, lineHeight: 1.35 }}>
                {bestFinal === 0 ? 'Free' : (
                  best!.pass.discount.label || best!.pass.discount.class
                )}
                {' '}
                <span style={{ color: 'var(--ink-3)', fontWeight: 400 }}>
                  with {best!.library.name}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5" style={{ fontSize: 11, color: 'var(--ink-3)' }}>
                {bucket.digital > 0 && (
                  <span>⚡ {bucket.digital} digital</span>
                )}
                {bucket['physical-coupon'] > 0 && (
                  <span>🎫 {bucket['physical-coupon']} pickup</span>
                )}
                {bucket['loan-card'] > 0 && (
                  <span>🔁 {bucket['loan-card']} loan</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer: price summary + CTA */}
      {!isGuestOrEmpty && totalDiscounts > 0 && (
        <div className="flex items-center justify-between gap-2 px-3 py-2.5"
          style={{ borderTop: '1px solid var(--rule)', background: 'var(--bg)' }}>
          <div>
            {adult != null && bestFinal != null && bestFinal !== adult ? (
              <>
                <span style={{ fontSize: 12, color: 'var(--ink-3)', textDecoration: 'line-through' }}>
                  {fmtMoney(adult)}
                </span>
                <span className="mx-1.5" style={{ color: 'var(--ink-3)' }}>→</span>
                <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--g)' }}>
                  {bestFinal === 0 ? 'Free' : fmtMoney(bestFinal)}
                </span>
              </>
            ) : adult != null ? (
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink-2)' }}>
                {fmtMoney(adult)}
              </span>
            ) : (
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--g)' }}>
                {best?.pass.discount.label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 px-3 py-1.5 rounded-md"
            style={{ background: 'var(--g)', color: 'var(--white)', fontSize: 12, fontWeight: 500 }}>
            View {totalDiscounts} option{totalDiscounts === 1 ? '' : 's'}
            <span aria-hidden>→</span>
          </div>
        </div>
      )}
    </Link>
  );
}
