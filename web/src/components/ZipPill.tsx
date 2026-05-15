import { useEffect, useRef, useState } from 'react';
import { useCardpack } from '../stores/cardpack';

/**
 * Confirmed-state ZIP display for the TopBar.
 *
 * Default look: "📍 Your location · 01880 ✏"
 * Click to edit:  "📍 Your location · [01880] ✓"
 *
 * Persists via the cardpack store, namespaced by the current user (or 'guest').
 * Click anywhere in the pill (default mode) or the pencil icon to enter edit mode.
 */
export function ZipPill() {
  const zip = useCardpack(s => s.pack.zip);
  const saveZip = useCardpack(s => s.saveZip);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(zip);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setDraft(zip); }, [zip]);
  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commit = () => {
    const cleaned = draft.replace(/\D/g, '').slice(0, 5);
    if (cleaned.length === 0 || cleaned.length === 5) {
      saveZip(cleaned);
      setEditing(false);
    }
  };

  const cancel = () => {
    setDraft(zip);
    setEditing(false);
  };

  if (editing) {
    return (
      <div
        className="flex items-center gap-1.5 rounded-md"
        style={{
          background: 'var(--white)',
          border: '1px solid var(--g)',
          padding: '4px 8px',
          fontSize: 12,
        }}
      >
        <span style={{ color: 'var(--ink-3)', fontSize: 10 }}>your location</span>
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value.replace(/\D/g, '').slice(0, 5))}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') cancel();
          }}
          onBlur={commit}
          placeholder="01880"
          maxLength={5}
          inputMode="numeric"
          autoFocus
          style={{
            width: 56,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            fontSize: 13,
            fontWeight: 500,
            color: 'var(--ink-2)',
            padding: 0,
          }}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      aria-label="Edit your ZIP code"
      className="flex items-center gap-1.5 rounded-md"
      style={{
        background: 'transparent',
        border: '1px solid var(--rule)',
        padding: '4px 8px',
        cursor: 'pointer',
      }}
    >
      <span aria-hidden style={{ fontSize: 12, color: 'var(--ink-3)' }}>📍</span>
      <div className="flex flex-col items-start leading-tight">
        <span style={{ fontSize: 9, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          your location
        </span>
        <span style={{ fontSize: 12, fontWeight: 600, color: zip ? 'var(--ink-2)' : 'var(--ink-3)' }}>
          {zip || 'set ZIP'}
        </span>
      </div>
      <span aria-hidden style={{ fontSize: 11, color: 'var(--ink-3)', marginLeft: 2 }}>✏</span>
    </button>
  );
}
