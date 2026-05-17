interface Props {
  month: string;                       // 'YYYY-MM'
  selectedDate: string | null;
  todayIso: string;
  availableCounts: Record<string, number>;  // ISO date → # of usable coupons
  onSelect: (iso: string) => void;
}

const DOW_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export function CouponCalendar({ month, selectedDate, todayIso, availableCounts, onSelect }: Props) {
  const [yStr, mStr] = month.split('-');
  const year = Number(yStr);
  const monthNum = Number(mStr);
  const firstDow = new Date(year, monthNum - 1, 1).getDay();  // 0 = Sun
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
          const count = availableCounts[c.iso] ?? 0;
          const isPast = c.iso < todayIso;
          const isToday = c.iso === todayIso;
          const isSelected = c.iso === selectedDate;
          const interactive = !isPast;
          const hasAny = count > 0;

          const bg = isSelected
            ? 'var(--g)'
            : hasAny ? 'var(--g-pale)' : 'transparent';
          const fg = isSelected
            ? 'var(--white)'
            : isPast ? 'var(--ink-3)' : 'var(--ink-2)';

          return (
            <button
              key={i}
              type="button"
              disabled={!interactive}
              onClick={() => onSelect(c.iso)}
              className="rounded"
              style={{
                background: bg,
                border: isToday && !isSelected ? '1px solid var(--g)' : '1px solid transparent',
                color: fg,
                cursor: interactive ? 'pointer' : 'default',
                opacity: isPast ? 0.4 : 1,
                padding: '6px 0 4px',
                fontSize: 13,
                fontWeight: isSelected ? 600 : 500,
                lineHeight: 1.1,
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
              }}
            >
              <span>{c.day}</span>
              <span style={{
                fontSize: 10,
                color: isSelected ? 'var(--white)' : (hasAny ? 'var(--g)' : 'transparent'),
                lineHeight: 1,
                minHeight: 10,
              }}>
                {hasAny ? `${count}` : '·'}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
