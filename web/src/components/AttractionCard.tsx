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

const TYPE_STYLE = {
  'digital':         { icon: '⚡', label: 'Digital',   bg: 'var(--g-pale)',  fg: 'var(--g)'  },
  'physical-coupon': { icon: '🎫', label: 'Pickup',    bg: 'var(--au-pale)', fg: 'var(--au)' },
  'loan-card':       { icon: '🔁', label: 'Pickup & return', bg: 'var(--or-pale)', fg: 'var(--or)' },
  'unknown':         { icon: '?',  label: 'Unknown',   bg: 'var(--paper)',   fg: 'var(--ink-3)' },
} as const;

function heroSrc(a: Attraction): string {
  if (a.hero_image?.local_path) {
    const filename = a.hero_image.local_path.split(/[\\/]/).pop() ?? '';
    if (filename) return `/images/${filename}`;
  }
  const cat = a.categories?.[0]?.toLowerCase() ?? 'default';
  const known = ['family','children','history','nature','art','science','ocean','recreation'];
  const slug = known.includes(cat) ? cat : 'default';
  return `/placeholders/${slug}.svg`;
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null) return '';
  if (v === 0) return 'Free';
  if (Number.isInteger(v)) return `$${v}`;
  return `$${v.toFixed(2)}`;
}

function townFromAddress(addr: string): string {
  // Extract town from "123 Main St, Townname, MA 01234" or similar
  const m = addr.match(/,\s*([^,]+?),\s*[A-Z]{2}\s+\d{5}/);
  return m ? m[1].trim() : '';
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
}: Props) {
  const town = townFromAddress(attraction.address) || (attraction.categories[0] ?? '');
  const adult = attraction.original_price?.adult ?? null;
  const child = attraction.original_price?.child ?? null;

  return (
    <Link
      to={`/attractions/${attraction.slug}`}
      className="block bg-white border border-[color:var(--rule)] rounded-md overflow-hidden mb-4 hover:border-[color:var(--rule-strong)] transition-colors"
      style={{ color: 'inherit', textDecoration: 'none' }}
    >
      {/* Top section: attraction info */}
      <div className="flex flex-col sm:flex-row">
        <div className="relative w-full h-48 sm:w-64 sm:h-auto sm:min-h-[200px] flex-shrink-0">
          <img
            src={heroSrc(attraction)}
            alt=""
            loading="lazy"
            className="w-full h-full object-cover bg-[color:var(--paper)]"
          />
          <div className="absolute top-2 right-2 bg-white/85 rounded-full px-1 py-0.5">
            <FavoriteButton slug={attraction.slug} size={20} />
          </div>
        </div>
        <div className="flex-grow min-w-0 p-3 sm:p-4">
          <h3 className="font-serif" style={{ fontSize: 18, color: 'var(--ink-2)', fontWeight: 700, lineHeight: 1.25 }}>
            {attraction.museum_name}
          </h3>
          {town && (
            <p className="text-xs mt-1" style={{ color: 'var(--ink-3)' }}>{town}</p>
          )}
          {attraction.categories.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {attraction.categories.slice(0, 4).map(c => (
                <span key={c} className="text-[11px] px-2 py-0.5 rounded-full"
                  style={{ background: 'var(--paper)', color: 'var(--ink-3)' }}>
                  {c}
                </span>
              ))}
            </div>
          )}
          {adult != null && (
            <p className="mt-3 text-sm" style={{ color: 'var(--ink-2)' }}>
              From <span className="font-semibold">{fmtMoney(adult)}</span>
              <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>{' '}/ adult</span>
              {child != null && (
                <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>{', '}{fmtMoney(child)}{' '}/ child</span>
              )}
            </p>
          )}
        </div>
      </div>

      {/* Bottom section: discount options */}
      <div style={{ borderTop: '1px solid var(--rule)', background: 'var(--bg)' }}>
        {isGuestOrEmpty ? (
          <div className="p-3 sm:p-4 text-xs italic" style={{ color: 'var(--ink-3)' }}>
            Sign in to view {sourceCountForGuest} discount option{sourceCountForGuest === 1 ? '' : 's'} at this attraction
          </div>
        ) : pickedTags.length === 0 ? (
          <div className="p-3 sm:p-4 text-xs" style={{ color: 'var(--ink-3)' }}>
            No passes available for the selected date
          </div>
        ) : (
          <div className="p-2 sm:p-3 divide-y" style={{ borderColor: 'var(--rule)' }}>
            <div className="text-[11px] uppercase tracking-wider px-1 pb-2"
              style={{ color: 'var(--ink-3)', letterSpacing: '0.08em' }}>
              Discounts available with your cards
            </div>
            {pickedTags.map((t, i) => {
              const style = TYPE_STYLE[t.pass.pass_type];
              const finalPrice = applyDiscount(attraction.original_price, t.pass.discount);
              const showStrike = adult != null && finalPrice != null && finalPrice !== adult;
              const isDigital = t.pass.pass_type === 'digital';
              return (
                <div key={`${t.pass.library_id}-${i}`} className="flex items-center gap-2 sm:gap-3 px-1 py-2"
                  style={{ borderColor: 'var(--rule)' }}>
                  <span aria-hidden style={{
                    background: style.bg, color: style.fg,
                    width: 28, height: 28, borderRadius: 14,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, flexShrink: 0,
                  }}>{style.icon}</span>
                  <div className="flex-grow min-w-0">
                    <div className="text-[13px] font-medium" style={{ color: 'var(--ink-2)' }}>
                      {style.label}
                      {!isDigital && (
                        <span className="font-normal" style={{ color: 'var(--ink-3)' }}>
                          {' · '}{t.library.town}
                          {t.distanceMi != null && ` · ${Math.round(t.distanceMi)} mi`}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px]" style={{ color: 'var(--ink-3)' }}>
                      {t.pass.discount.label || t.pass.discount.class}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    {showStrike ? (
                      <>
                        <span className="text-[11px] line-through mr-1" style={{ color: 'var(--ink-3)' }}>
                          {fmtMoney(adult)}
                        </span>
                        <span className="text-[14px] font-semibold" style={{ color: style.fg }}>
                          {fmtMoney(finalPrice)}
                        </span>
                      </>
                    ) : finalPrice === 0 ? (
                      <span className="text-[14px] font-semibold" style={{ color: style.fg }}>Free</span>
                    ) : (
                      <span className="text-[12px]" style={{ color: style.fg, fontWeight: 500 }}>
                        {t.pass.discount.label || '—'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Link>
  );
}
