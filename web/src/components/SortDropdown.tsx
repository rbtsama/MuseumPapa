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

/**
 * Compact pill-style sort selector. Uses HeroUI Dropdown for a popover menu
 * instead of HeroUI Select (which forces a labeled input look).
 */
export function SortDropdown({ value, onChange, distanceEnabled }: Props) {
  return (
    <Dropdown>
      <DropdownTrigger>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md cursor-pointer"
          style={{
            background: 'transparent',
            border: '1px solid var(--rule)',
            padding: '6px 10px',
            fontSize: 12,
            color: 'var(--ink-2)',
          }}
        >
          <span aria-hidden style={{ fontSize: 13, color: 'var(--ink-3)' }}>↕</span>
          <span style={{ fontWeight: 500 }}>{LABELS[value]}</span>
          <span aria-hidden style={{ color: 'var(--ink-3)', fontSize: 10, marginLeft: 2 }}>▾</span>
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
