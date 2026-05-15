import { useMemo } from 'react';
import type { Attraction } from '../data/types';

interface Props {
  attractions: Attraction[];
  value: string;                       // 'all' | 'favorites' | a category name
  onChange: (v: string) => void;
  maxChips?: number;                   // categories beyond ALL + FAVORITES
  favoritesCount: number;
}

const ALL = 'all';
const FAVORITES = 'favorites';

/**
 * Compact square-ish chip row, mobile-first multi-line layout.
 *
 * Order: [ALL] [♡ FAVORITES] then top-N category chips by frequency.
 * Favorites chip has a distinct unselected border color (rd) to signal
 * it's not a regular category but a special "your saved items" filter.
 */
export function CategoryChips({ attractions, value, onChange, maxChips = 10, favoritesCount }: Props) {
  const top = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of attractions) {
      for (const c of a.categories) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxChips)
      .map(([name, count]) => ({ name, count }));
  }, [attractions, maxChips]);

  const renderChip = (
    key: string,
    label: string,
    count: number,
    opts?: { specialBorderColor?: string },
  ) => {
    const selected = value === key;
    return (
      <button
        key={key}
        type="button"
        onClick={() => onChange(key)}
        className="rounded-md whitespace-nowrap"
        style={{
          padding: '4px 10px',
          fontSize: 11,
          fontWeight: 500,
          border: selected
            ? '1px solid var(--g)'
            : `1px solid ${opts?.specialBorderColor ?? 'var(--rule)'}`,
          background: selected ? 'var(--g)' : 'var(--white)',
          color: selected ? 'var(--white)' : (opts?.specialBorderColor ?? 'var(--ink-2)'),
          cursor: 'pointer',
          transition: 'background 0.1s, border-color 0.1s',
          lineHeight: 1.4,
        }}
      >
        {label}
        <span
          className="ml-1.5"
          style={{
            fontSize: 10,
            color: selected ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
            fontWeight: 400,
          }}
        >
          {count}
        </span>
      </button>
    );
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {renderChip(ALL, 'All', attractions.length)}
      {renderChip(FAVORITES, '♡ Favorites', favoritesCount, { specialBorderColor: 'var(--rd)' })}
      {top.map(c => renderChip(c.name, c.name, c.count))}
    </div>
  );
}
