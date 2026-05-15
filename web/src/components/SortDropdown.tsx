import { Select, SelectItem } from '@heroui/react';

export type SortOption = 'recommended' | 'alpha' | 'distance';

interface Props {
  value: SortOption;
  onChange: (v: SortOption) => void;
  distanceEnabled: boolean;
}

/**
 * Three sort modes:
 *   - recommended (default): favorites first → distance asc → A-Z (tie-break)
 *   - alpha: pure A-Z; favorites NOT pinned
 *   - distance: distance asc; favorites NOT pinned (requires ZIP)
 *
 * Rationale: only "Recommended" pins favorites — the other two are
 * mechanical sorts where the user expects the pure ordering.
 */
export function SortDropdown({ value, onChange, distanceEnabled }: Props) {
  return (
    <Select
      label="Sort"
      labelPlacement="outside"
      size="sm"
      selectedKeys={new Set([value])}
      onSelectionChange={(keys) => {
        const first = Array.from(keys)[0] as SortOption | undefined;
        if (first) onChange(first);
      }}
      classNames={{ base: 'max-w-[180px]' }}
    >
      <SelectItem key="recommended">Recommended</SelectItem>
      <SelectItem key="alpha">A–Z</SelectItem>
      <SelectItem key="distance" textValue="Distance">
        {distanceEnabled ? 'Distance' : 'Distance (set ZIP)'}
      </SelectItem>
    </Select>
  );
}
