import { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';

export type SortOption = 'recommended' | 'alpha' | 'distance';

const LABELS: Record<SortOption, string> = {
  recommended: 'Recommended',
  alpha: 'A–Z',
  distance: 'Distance',
};

interface Props {
  value: SortOption;
  onChange: (v: SortOption) => void;
  distanceEnabled: boolean;
}

export function SortDropdown({ value, onChange, distanceEnabled }: Props) {
  const isDefault = value === 'recommended';
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
          }}>↕</span>
          <span style={{ fontWeight: 500 }}>{isDefault ? 'Sort' : LABELS[value]}</span>
          <span aria-hidden style={{
            color: isDefault ? 'var(--ink-3)' : 'var(--white)',
            fontSize: 11, marginLeft: 2,
          }}>▾</span>
        </button>
      </DropdownTrigger>
      <DropdownMenu
        aria-label="Sort by"
        selectedKeys={new Set([value])}
        selectionMode="single"
        onAction={(key) => onChange(key as SortOption)}
        disabledKeys={distanceEnabled ? undefined : ['distance']}
      >
        <DropdownItem key="recommended">Recommended</DropdownItem>
        <DropdownItem key="alpha">A–Z</DropdownItem>
        <DropdownItem key="distance">Distance</DropdownItem>
      </DropdownMenu>
    </Dropdown>
  );
}
