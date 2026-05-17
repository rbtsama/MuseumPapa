import { useMemo } from 'react';
import type { Attraction } from '../data/types';

interface Props {
  attractions: Attraction[];
  value: string;                       // 'all' or a category name
  onChange: (v: string) => void;
  maxChips?: number;
}

const ALL = 'all';

export function CategoryChips({ attractions, value, onChange, maxChips = 10 }: Props) {
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

  const renderChip = (key: string, label: string, count: number) => {
    const selected = value === key;
    return (
      <button
        key={key}
        type="button"
        onClick={() => onChange(key)}
        className="rounded-md whitespace-nowrap"
        style={{
          padding: '4px 10px',
          fontSize: 12,
          fontWeight: 500,
          border: selected ? '1px solid var(--g)' : '1px solid var(--rule)',
          background: selected ? 'var(--g)' : 'var(--white)',
          color: selected ? 'var(--white)' : 'var(--ink-2)',
          cursor: 'pointer',
          transition: 'background 0.1s, border-color 0.1s',
          lineHeight: 1.4,
        }}
      >
        {label}
        <span className="ml-1.5" style={{
          fontSize: 11,
          color: selected ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
          fontWeight: 400,
        }}>
          {count}
        </span>
      </button>
    );
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {renderChip(ALL, 'All', attractions.length)}
      {top.map(c => renderChip(c.name, c.name, c.count))}
    </div>
  );
}
