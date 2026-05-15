import { Input } from '@heroui/react';

interface Props {
  value: string;          // YYYY-MM-DD
  onChange: (v: string) => void;
}

export function DatePicker({ value, onChange }: Props) {
  return (
    <Input
      type="date"
      label="Date"
      labelPlacement="outside"
      size="sm"
      value={value}
      onValueChange={onChange}
      classNames={{ base: 'max-w-[170px]' }}
    />
  );
}
