import { Select, SelectItem } from '@heroui/react';

export type SortOption = 'favorites' | 'alpha' | 'distance' | 'discount';

interface Props {
  value: SortOption;
  onChange: (v: SortOption) => void;
  distanceEnabled: boolean;
}

export function SortDropdown({ value, onChange, distanceEnabled }: Props) {
  return (
    <Select
      label="Sort by"
      labelPlacement="outside-left"
      size="sm"
      selectedKeys={new Set([value])}
      onSelectionChange={(keys) => {
        const first = Array.from(keys)[0] as SortOption | undefined;
        if (first) onChange(first);
      }}
      className="max-w-xs"
    >
      <SelectItem key="favorites">Favorites first</SelectItem>
      <SelectItem key="alpha">A–Z</SelectItem>
      <SelectItem key="distance" textValue="Distance">
        {distanceEnabled ? 'Distance' : 'Distance (set ZIP)'}
      </SelectItem>
      <SelectItem key="discount">Discount</SelectItem>
    </Select>
  );
}
