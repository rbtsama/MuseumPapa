import { useRef } from 'react';
import { formatFriendlyDate } from '../lib/dates';
import { CalendarIcon } from './icons';

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export function DatePicker({ value, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const openPicker = () => {
    const el = inputRef.current;
    if (!el) return;
    // showPicker() is the reliable cross-browser API; fall back to focus+click
    // for older browsers where it's not yet available.
    type WithShowPicker = HTMLInputElement & { showPicker?: () => void };
    const withPicker = el as WithShowPicker;
    if (typeof withPicker.showPicker === 'function') {
      withPicker.showPicker();
    } else {
      el.focus();
      el.click();
    }
  };

  return (
    <button
      type="button"
      onClick={openPicker}
      className="inline-flex items-center gap-1.5 rounded-md cursor-pointer"
      style={{
        background: 'transparent',
        border: '1px solid var(--rule)',
        padding: '6px 10px',
        fontSize: 12,
        color: 'var(--ink-2)',
      }}
    >
      <CalendarIcon style={{ color: 'var(--ink-3)' }} />
      <span style={{ fontWeight: 500 }}>{formatFriendlyDate(value)}</span>
      <input
        ref={inputRef}
        type="date"
        value={value}
        onChange={(e) => { if (e.target.value) onChange(e.target.value); }}
        style={{
          position: 'absolute',
          width: 1, height: 1,
          opacity: 0, pointerEvents: 'none',
        }}
        tabIndex={-1}
        aria-hidden
      />
    </button>
  );
}
