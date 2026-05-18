import { useEffect, useState } from 'react';
import { useCardpack } from '../stores/cardpack';
import { geocodeZip } from '../lib/distance';

interface Props {
  onDark?: boolean;
}

/**
 * ZIP input. Three states:
 *   - empty → no error styling, no distance computation downstream
 *   - 5-digit valid → saved to cardpack, distance computations enabled
 *   - 5-digit invalid (geocoder miss) OR <5 digits → red border + inline hint,
 *     NOT persisted to cardpack (last valid value stays)
 */
export function ZipPill({ onDark = false }: Props) {
  const zip = useCardpack(s => s.pack.zip);
  const saveZip = useCardpack(s => s.saveZip);
  const [draft, setDraft] = useState(zip);
  const [validating, setValidating] = useState(false);
  const [invalidReason, setInvalidReason] = useState<string | null>(null);

  useEffect(() => { setDraft(zip); }, [zip]);

  const commit = async () => {
    const cleaned = draft.replace(/\D/g, '').slice(0, 5);
    setDraft(cleaned);
    if (cleaned === zip) { setInvalidReason(null); return; }
    if (cleaned === '') {
      setInvalidReason(null);
      saveZip('');
      return;
    }
    if (cleaned.length < 5) {
      setInvalidReason('Need 5 digits');
      return;
    }
    setValidating(true);
    const g = await geocodeZip(cleaned);
    setValidating(false);
    if (!g) {
      setInvalidReason('Not a valid US ZIP');
      return;
    }
    setInvalidReason(null);
    saveZip(cleaned);
  };

  const handleChange = (v: string) => {
    setDraft(v.replace(/\D/g, '').slice(0, 5));
    if (invalidReason) setInvalidReason(null);
  };

  const isInvalid = invalidReason != null;
  const labelColor = onDark ? 'rgba(255,255,255,0.72)' : 'var(--ink-3)';
  const okBorder = onDark ? 'rgba(255,255,255,0.4)' : 'var(--rule)';
  const okText = onDark ? 'var(--white)' : 'var(--ink-2)';
  const okBg = onDark ? 'rgba(255,255,255,0.12)' : 'var(--white)';
  // Error state: switch to a solid white bubble so the red border + red text
  // stay readable even on the dark-green TopBar.
  const inputBg = isInvalid ? 'var(--white)' : okBg;
  const inputText = isInvalid ? 'var(--rd)' : okText;
  const inputBorder = isInvalid ? 'var(--rd)' : okBorder;

  return (
    <div className="inline-flex items-center gap-2">
      <span style={{
        fontSize: 11, color: labelColor,
        textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap',
      }}>ZIP code</span>
      <div style={{ position: 'relative' }}>
        <input
          value={draft}
          onChange={(e) => handleChange(e.target.value)}
          onBlur={() => { void commit(); }}
          onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
          placeholder="01880"
          inputMode="numeric"
          maxLength={5}
          aria-invalid={isInvalid}
          aria-label="Your ZIP code"
          style={{
            width: 70,
            padding: '5px 8px',
            border: `1px solid ${inputBorder}`,
            borderRadius: 4,
            fontSize: 13, fontWeight: 600, textAlign: 'center',
            color: inputText,
            background: inputBg,
            outline: 'none',
            opacity: validating ? 0.6 : 1,
            transition: 'border-color 0.12s, color 0.12s, background 0.12s',
          }}
        />
        {invalidReason && (
          <span
            role="alert"
            style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              right: 0,
              padding: '4px 8px',
              background: 'var(--white)',
              border: '1px solid var(--rd)',
              borderRadius: 4,
              color: 'var(--rd)',
              fontSize: 11,
              fontWeight: 500,
              whiteSpace: 'normal',
              maxWidth: 200,
              lineHeight: 1.4,
              zIndex: 50,
              boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
              pointerEvents: 'none',
            }}
          >{invalidReason}</span>
        )}
      </div>
    </div>
  );
}
