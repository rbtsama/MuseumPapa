import { useEffect, useState } from 'react';
import { useCardpack } from '../stores/cardpack';
import { geocodeZip } from '../lib/distance';

/**
 * Static layout: [your location] [BOX with ZIP]
 *
 * The box is always an <input>: empty shows the placeholder, populated
 * shows the digits in bold. No icons, no edit-mode toggle — the box's
 * border conveys editability.
 *
 * Validation is permissive: we save whatever the user types, but if the
 * value is incomplete (<5 digits) or the geocoder can't find a match,
 * the box and text turn red so the user knows something's off without
 * being blocked from continuing.
 */
export function ZipPill() {
  const zip = useCardpack(s => s.pack.zip);
  const saveZip = useCardpack(s => s.saveZip);
  const [draft, setDraft] = useState(zip);
  const [geoMissing, setGeoMissing] = useState(false);

  useEffect(() => { setDraft(zip); }, [zip]);

  // Check whether the saved ZIP can actually be geocoded. Result is cached
  // by geocodeZip itself, so repeated checks are free after the first hit.
  useEffect(() => {
    if (!zip || zip.length !== 5) { setGeoMissing(false); return; }
    let cancelled = false;
    geocodeZip(zip).then(g => { if (!cancelled) setGeoMissing(!g); });
    return () => { cancelled = true; };
  }, [zip]);

  const commit = () => {
    const cleaned = draft.replace(/\D/g, '').slice(0, 5);
    setDraft(cleaned);
    if (cleaned !== zip) saveZip(cleaned);
  };

  const isIncomplete = draft.length > 0 && draft.length < 5;
  const isInvalid = isIncomplete || (draft.length === 5 && geoMissing);

  return (
    <div className="inline-flex items-center gap-2">
      <span
        style={{
          fontSize: 10,
          color: 'var(--ink-3)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          whiteSpace: 'nowrap',
        }}
      >
        your location
      </span>
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value.replace(/\D/g, '').slice(0, 5))}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
        placeholder="01880"
        inputMode="numeric"
        maxLength={5}
        aria-invalid={isInvalid}
        aria-label="Your ZIP code"
        style={{
          width: 70,
          padding: '5px 8px',
          border: `1px solid ${isInvalid ? 'var(--rd)' : 'var(--rule)'}`,
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 600,
          textAlign: 'center',
          color: isInvalid ? 'var(--rd)' : 'var(--ink-2)',
          background: 'var(--white)',
          outline: 'none',
          transition: 'border-color 0.12s, color 0.12s',
        }}
        onFocus={(e) => {
          // light visual cue that it's now actively editable
          if (!isInvalid) e.currentTarget.style.borderColor = 'var(--g)';
        }}
        onBlurCapture={(e) => {
          if (!isInvalid) e.currentTarget.style.borderColor = 'var(--rule)';
        }}
      />
    </div>
  );
}
