import { Link } from 'react-router';
import type { Attraction } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';
import { PassTag } from './PassTag';
import { FavoriteButton } from './FavoriteButton';
import { formatPriceLine } from '../lib/price-fallback';

interface Props {
  attraction: Attraction;
  pickedTags: PickedTag[];
  isGuestOrEmpty?: boolean;
  sourceCountForGuest?: number; // shown only when isGuestOrEmpty
}

function heroSrc(a: Attraction): string {
  if (a.hero_image?.local_path) {
    // local_path is like 'static/images/mos.jpg' or 'data/static/images/mos.jpg'
    // We mirrored these into web/public/images/, so use just '/images/<slug>.<ext>'.
    const filename = a.hero_image.local_path.split(/[\\/]/).pop() ?? '';
    if (filename) return `/images/${filename}`;
  }
  const cat = a.categories?.[0]?.toLowerCase() ?? 'default';
  const known = ['family','children','history','nature','art','science','ocean','recreation'];
  const slug = known.includes(cat) ? cat : 'default';
  return `/placeholders/${slug}.svg`;
}

export function AttractionCard({
  attraction, pickedTags, isGuestOrEmpty = false, sourceCountForGuest = 0,
}: Props) {
  const primaryDiscount = pickedTags[0]?.pass.discount ?? null;
  const priceLine = formatPriceLine(attraction.original_price, primaryDiscount);
  const introSnippet = attraction.categories.slice(0, 3).join(' · ');

  return (
    <Link to={`/attractions/${attraction.slug}`} style={{
      display: 'block',
      borderBottom: '1px solid var(--rule)',
      padding: '12px 8px',
      color: 'inherit',
      textDecoration: 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <FavoriteButton slug={attraction.slug} />
        <img
          src={heroSrc(attraction)}
          alt=""
          loading="lazy"
          style={{
            width: 80, height: 80, borderRadius: 4, objectFit: 'cover',
            background: 'var(--paper)', flexShrink: 0,
          }}
        />
        <div style={{ flexGrow: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
            <div className="font-serif" style={{ fontSize: 16, color: 'var(--ink-2)', fontWeight: 700 }}>
              {attraction.museum_name}
            </div>
            {priceLine && (
              <div style={{ fontSize: 12, color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
                {priceLine}
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>
            {introSnippet || ' '}
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {isGuestOrEmpty ? (
              <span style={{ fontSize: 12, color: 'var(--ink-3)', fontStyle: 'italic' }}>
                Sign in to view {sourceCountForGuest} discount option{sourceCountForGuest === 1 ? '' : 's'}
              </span>
            ) : pickedTags.length === 0 ? (
              <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>No passes available</span>
            ) : pickedTags.map((t, i) => (
              <PassTag
                key={`${t.pass.library_id}-${i}`}
                passType={t.pass.pass_type}
                discountLabel={t.pass.discount.label || t.pass.discount.class}
                libraryTown={t.library.town}
                distanceMi={t.distanceMi}
              />
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
}
