import { useEffect, useState } from 'react';
import { Input } from '@heroui/react';
import { useCardpack } from '../stores/cardpack';

/**
 * Small ZIP input that lives in the filter bar.
 * Writes through to the cardpack store, which persists to localStorage —
 * namespaced by username (or 'guest' if not signed in).
 */
export function ZipInput() {
  const zip = useCardpack(s => s.pack.zip);
  const saveZip = useCardpack(s => s.saveZip);
  const [draft, setDraft] = useState(zip);

  useEffect(() => { setDraft(zip); }, [zip]);

  const commit = (v: string) => {
    const cleaned = v.replace(/\D/g, '').slice(0, 5);
    setDraft(cleaned);
    if (cleaned.length === 0 || cleaned.length === 5) {
      saveZip(cleaned);
    }
  };

  return (
    <Input
      label="Your ZIP"
      labelPlacement="outside-left"
      size="sm"
      value={draft}
      onValueChange={commit}
      placeholder="01880"
      maxLength={5}
      className="max-w-[180px]"
      description={zip && zip.length === 5 ? undefined : 'Enables distance sort'}
    />
  );
}
