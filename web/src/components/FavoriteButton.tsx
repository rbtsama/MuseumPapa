import { useFavorites } from '../stores/favorites';

interface Props {
  slug: string;
  size?: number;
}

export function FavoriteButton({ slug, size = 18 }: Props) {
  const isFav = useFavorites(s => s.isFavorite(slug));
  const toggle = useFavorites(s => s.toggle);

  return (
    <button
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggle(slug); }}
      aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
      style={{
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        fontSize: `${size}px`,
        lineHeight: 1,
        color: isFav ? 'var(--rd)' : 'var(--ink-3)',
        padding: '2px',
      }}
    >
      {isFav ? '❤' : '♡'}
    </button>
  );
}
