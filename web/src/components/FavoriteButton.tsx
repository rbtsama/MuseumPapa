import { useFavorites } from '../stores/favorites';
import { HeartIcon } from './icons';

interface Props {
  slug: string;
  /** 'inline' = bare icon for text flow; 'overlay' = floating white badge on a card corner. */
  variant?: 'inline' | 'overlay';
}

const ICON_SIZE = 18;
const BTN_SIZE = 32;  // visual hit target, identical for both variants

export function FavoriteButton({ slug, variant = 'inline' }: Props) {
  const isFav = useFavorites(s => s.isFavorite(slug));
  const toggle = useFavorites(s => s.toggle);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggle(slug);
  };

  const common = {
    width: BTN_SIZE,
    height: BTN_SIZE,
    borderRadius: BTN_SIZE / 2,
    display: 'inline-flex' as const,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    cursor: 'pointer' as const,
    padding: 0,
    lineHeight: 1,
    transition: 'background 0.1s, transform 0.1s',
    color: isFav ? 'var(--rd)' : 'var(--ink-2)',
  };

  if (variant === 'overlay') {
    return (
      <button
        type="button"
        onClick={handleClick}
        aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
        aria-pressed={isFav}
        style={{
          ...common,
          background: 'rgba(255,255,255,0.88)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
          border: '1px solid rgba(0,0,0,0.06)',
          boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
        }}
      >
        <HeartIcon filled={isFav} size={ICON_SIZE} />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
      aria-pressed={isFav}
      style={{ ...common, background: 'transparent', border: 'none' }}
    >
      <HeartIcon filled={isFav} size={ICON_SIZE} />
    </button>
  );
}
