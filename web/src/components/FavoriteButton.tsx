import { useFavorites } from '../stores/favorites';

interface Props {
  slug: string;
  /** Visual variant.
   *  - 'inline' (default): bare icon with padded hit-area, for text-flow contexts.
   *  - 'overlay':          circular white-translucent badge for absolute-positioning
   *                         over an image (Booking.com / Airbnb pattern). */
  variant?: 'inline' | 'overlay';
  /** Icon glyph size in px. Defaults: inline=18, overlay=22. */
  size?: number;
}

export function FavoriteButton({ slug, variant = 'inline', size }: Props) {
  const isFav = useFavorites(s => s.isFavorite(slug));
  const toggle = useFavorites(s => s.toggle);
  const iconSize = size ?? (variant === 'overlay' ? 22 : 18);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggle(slug);
  };

  if (variant === 'overlay') {
    return (
      <button
        type="button"
        onClick={handleClick}
        aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
        aria-pressed={isFav}
        style={{
          // 40x40 button — close to Apple HIG 44pt minimum for touch targets
          width: 40,
          height: 40,
          borderRadius: 20,
          background: 'rgba(255,255,255,0.88)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          border: '1px solid rgba(0,0,0,0.06)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          padding: 0,
          color: isFav ? 'var(--rd)' : 'var(--ink-2)',
          fontSize: iconSize,
          lineHeight: 1,
          transition: 'transform 0.1s, background 0.1s',
        }}
      >
        {isFav ? '❤' : '♡'}
      </button>
    );
  }

  // Inline (default): negative-margin hack expands hit target without
  // shifting surrounding layout.
  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
      aria-pressed={isFav}
      style={{
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        fontSize: `${iconSize}px`,
        lineHeight: 1,
        color: isFav ? 'var(--rd)' : 'var(--ink-3)',
        padding: 10,
        margin: -10,
      }}
    >
      {isFav ? '❤' : '♡'}
    </button>
  );
}
