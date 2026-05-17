import { useMemo } from 'react';
import { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';
import type { Attraction } from '../data/types';

interface Props {
  attractions: Attraction[];
  value: string;             // 'all' or a category name
  onChange: (v: string) => void;
  maxCategories?: number;
}

const ALL = 'all';

export function CategoryDropdown({ attractions, value, onChange, maxCategories = 12 }: Props) {
  const options = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of attractions) {
      for (const c of a.categories) counts.set(c, (counts.get(c) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxCategories)
      .map(([name, count]) => ({ name, count }));
  }, [attractions, maxCategories]);

  const isDefault = value === ALL;
  return (
    <Dropdown>
      <DropdownTrigger>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md cursor-pointer"
          style={{
            background: isDefault ? 'transparent' : 'var(--g)',
            border: `1px solid ${isDefault ? 'var(--rule)' : 'var(--g)'}`,
            padding: '6px 10px',
            fontSize: 12,
            color: isDefault ? 'var(--ink-2)' : 'var(--white)',
          }}
        >
          <span aria-hidden style={{
            fontSize: 13,
            color: isDefault ? 'var(--ink-3)' : 'var(--white)',
          }}>☰</span>
          <span style={{ fontWeight: 500 }}>{isDefault ? 'Category' : value}</span>
          <span aria-hidden style={{
            color: isDefault ? 'var(--ink-3)' : 'var(--white)',
            fontSize: 11, marginLeft: 2,
          }}>▾</span>
        </button>
      </DropdownTrigger>
      <DropdownMenu
        aria-label="Category"
        selectedKeys={new Set([value])}
        selectionMode="single"
        onAction={(key) => onChange(key as string)}
        items={[{ name: ALL, count: attractions.length }, ...options]}
      >
        {(item) => (
          <DropdownItem key={item.name}>
            {item.name === ALL ? `All (${item.count})` : `${item.name} (${item.count})`}
          </DropdownItem>
        )}
      </DropdownMenu>
    </Dropdown>
  );
}
