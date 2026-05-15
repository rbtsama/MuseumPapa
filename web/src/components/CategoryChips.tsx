import { useMemo } from 'react';
import type { Attraction } from '../data/types';

interface Props {
  attractions: Attraction[];
  value: string;                       // 'all' or a specific category name
  onChange: (v: string) => void;
  maxChips?: number;                   // how many categories to show beyond "All"
}

/**
 * Single-select chip row for category filtering.
 * Aggregates categories from the loaded attractions data and shows the most common.
 */
export function CategoryChips({ attractions, value, onChange, maxChips = 10 }: Props) {
  const top = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of attractions) {
      for (const c of a.categories) {
        counts.set(c, (counts.get(c) ?? 0) + 1);
      }
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxChips)
      .map(([name, count]) => ({ name, count }));
  }, [attractions, maxChips]);

  const ALL = 'all';
  const chips: { key: string; label: string; count: number }[] = [
    { key: ALL, label: 'All', count: attractions.length },
    ...top.map(c => ({ key: c.name, label: c.name, count: c.count })),
  ];

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {chips.map(c => {
        const selected = value === c.key;
        return (
          <button
            key={c.key}
            type="button"
            onClick={() => onChange(c.key)}
            style={{
              padding: '4px 12px',
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 500,
              border: selected ? '1px solid var(--g)' : '1px solid var(--rule)',
              background: selected ? 'var(--g)' : 'var(--white)',
              color: selected ? 'var(--white)' : 'var(--ink-2)',
              cursor: 'pointer',
              transition: 'background 0.1s',
            }}
          >
            {c.label}
            <span style={{
              marginLeft: 6,
              fontSize: 11,
              color: selected ? 'var(--g-pale)' : 'var(--ink-3)',
            }}>
              {c.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
