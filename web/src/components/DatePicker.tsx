interface Props {
  value: string;           // YYYY-MM-DD
  onChange: (v: string) => void;
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function tomorrowIso(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
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

/**
 * Pill-style date picker. Visually compact (icon + label + value on a single
 * line) while still triggering the browser's native date dialog for selection
 * — best UX on mobile (iOS Safari and Chrome both render a familiar picker).
 */
export function DatePicker({ value, onChange }: Props) {
  return (
    <label
      className="relative inline-flex items-center gap-1.5 rounded-md cursor-pointer"
      style={{
        background: 'transparent',
        border: '1px solid var(--rule)',
        padding: '6px 10px',
        fontSize: 12,
        minWidth: 180,
      }}
    >
      <span aria-hidden style={{ fontSize: 13, color: 'var(--ink-3)' }}>📅</span>
      <span style={{ color: 'var(--ink-3)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        Date
      </span>
      <span style={{ color: 'var(--ink-2)', fontWeight: 600, fontSize: 12 }}>
        {fmt(value)}
      </span>
      {/* invisible native input — captures clicks anywhere in the label */}
      <input
        type="date"
        value={value}
        onChange={(e) => e.target.value && onChange(e.target.value)}
        className="absolute inset-0"
        style={{ opacity: 0, cursor: 'pointer' }}
      />
    </label>
  );
}
