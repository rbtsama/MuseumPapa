import { useRef } from 'react';
import { todayIso, tomorrowIso } from '../lib/dates';

interface Props {
  value: string;
  onChange: (v: string) => void;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DOWS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function fmt(iso: string): string {
  if (iso === todayIso()) return `Today, ${shortDate(iso)}`;
  if (iso === tomorrowIso()) return `Tomorrow, ${shortDate(iso)}`;
  const d = new Date(iso + 'T00:00:00');
  return `${DOWS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

function shortDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
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
      <span aria-hidden style={{ fontSize: 13, color: 'var(--ink-3)' }}>📅</span>
      <span style={{ fontWeight: 500 }}>{fmt(value)}</span>
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
