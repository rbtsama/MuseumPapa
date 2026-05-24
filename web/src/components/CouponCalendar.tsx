interface CellInfo {
  best: string;          // "FREE" / "50%" / "$5" / ""
  isFree: boolean;       // for color emphasis
  status?: 'available' | 'booked' | 'closed' | 'none';  // optional for backward-compat
}

interface Props {
  month: string;                              // 'YYYY-MM'
  selectedDate: string | null;
  todayIso: string;
  cellInfo: Record<string, CellInfo>;         // ISO date → best-coupon summary
  onSelect: (iso: string) => void;
}

const DOW_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export function CouponCalendar({ month, selectedDate, todayIso, cellInfo, onSelect }: Props) {
  const [yStr, mStr] = month.split('-');
  const year = Number(yStr);
  const monthNum = Number(mStr);
  const firstDow = new Date(year, monthNum - 1, 1).getDay();
  const lastDay = daysInMonth(year, monthNum);

  const cells: Array<{ iso: string; day: number } | null> = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= lastDay; d++) {
    cells.push({ iso: `${yStr}-${mStr}-${pad(d)}`, day: d });
  }
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
        {DOW_LABELS.map((d, i) => (
          <div key={i} style={{ fontSize: 11, color: 'var(--ink-3)', textAlign: 'center', padding: '2px 0' }}>
            {d}
          </div>
        ))}
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
        {cells.map((c, i) => {
          if (!c) return <div key={i} />;
          const info = cellInfo[c.iso];
          const status = info?.status;
          const isPast = c.iso < todayIso;
          const isToday = c.iso === todayIso;
          const isSelected = c.iso === selectedDate;

          // A cell is interactive when not past AND not booked/closed.
          // (status values: 'available' | 'booked' | 'closed' | 'none' | undefined)
          const interactive = !isPast && status !== 'booked' && status !== 'closed';

          // Background: selected overrides everything; otherwise status-driven.
          const bg = isSelected
            ? 'var(--g)'
            : status === 'available' ? 'var(--g-pale)'
            : status === 'booked' ? 'var(--paper)'
            : status === 'closed' ? 'var(--paper)'
            : 'transparent';

          // Day number foreground.
          const dayFg = isSelected
            ? 'var(--white)'
            : isPast ? 'var(--ink-3)'
            : status === 'booked' ? 'var(--ink-3)'
            : status === 'closed' ? 'var(--rd)'
            : 'var(--ink-2)';

          // Coupon label foreground.
          const bestFg = isSelected
            ? 'var(--white)'
            : (info && info.isFree) ? 'var(--g)' : 'var(--g-2)';

          // Marker shown when status is booked/closed and best label is blank.
          const hasLabel = info != null && info.best !== '';
          const markerText = !hasLabel
            ? (status === 'closed' ? '×' : status === 'booked' ? '—' : '·')
            : info.best;

          return (
            <button
              key={i}
              type="button"
              disabled={!interactive}
              onClick={() => interactive ? onSelect(c.iso) : undefined}
              className="rounded"
              data-status={status ?? 'none'}
              style={{
                background: bg,
                border: isToday && !isSelected ? '1px solid var(--g)' : '1px solid transparent',
                color: dayFg,
                cursor: interactive ? 'pointer' : 'default',
                opacity: isPast ? 0.4 : (status === 'booked' || status === 'closed') ? 0.6 : 1,
                padding: '4px 0',
                lineHeight: 1.1,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
                minHeight: 44,
                justifyContent: 'center',
              }}
            >
              <span style={{
                fontSize: 13,
                fontWeight: isSelected ? 600 : 500,
                textDecoration: status === 'closed' && !isSelected ? 'line-through' : 'none',
              }}>{c.day}</span>
              <span style={{
                fontSize: 11,
                fontWeight: 700,
                color: hasLabel ? bestFg : 'var(--ink-3)',
                lineHeight: 1,
                minHeight: 11,
                letterSpacing: '-0.02em',
              }}>
                {markerText}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
