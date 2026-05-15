import { useEffect, useState } from 'react';
import { Input } from '@heroui/react';
import { useCardpack } from '../stores/cardpack';

/**
 * Always-visible ZIP input. Persists to the cardpack store (per-user, or
 * 'guest' namespace if not signed in).
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
      labelPlacement="outside"
      size="sm"
      value={draft}
      onValueChange={commit}
      placeholder="01880"
      maxLength={5}
      classNames={{ base: 'max-w-[150px]' }}
    />
  );
}
