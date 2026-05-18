import { useState } from 'react';
import { next7Days } from '../../lib/dateRange';
import { CouponCalendar } from '../CouponCalendar';

interface Props {
  todayIso: string;
  selectedDate: string;
  onSelect: (iso: string) => void;
  month: string;
  setMonth: (m: string) => void;
  cellInfo: Record<string, { best: string; isFree: boolean }>;
  monthPills: string[];
}

const DOW = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];

function pillLabel(iso: string, todayIso: string): string {
  if (iso === todayIso) return 'TODAY';
  const d = new Date(`${iso}T00:00:00`);
  return DOW[d.getDay()];
}

export function DayPillRow({
  todayIso, selectedDate, onSelect, month, setMonth, cellInfo, monthPills,
}: Props) {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const days = next7Days(todayIso);

  const handleDayClick = (iso: string) => {
    onSelect(iso);
    setCalendarOpen(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
        {days.map(iso => {
          const active = iso === selectedDate && !calendarOpen;
          const best = cellInfo[iso]?.best ?? '';
          return (
            <button
              key={iso}
              type="button"
              onClick={() => handleDayClick(iso)}
              style={{
                padding: '6px 12px', borderRadius: 14,
                border: `1px solid ${active ? 'var(--g)' : 'var(--rule)'}`,
                background: active ? 'var(--g)' : 'var(--white)',
                color: active ? 'var(--white)' : 'var(--ink-2)',
                fontSize: 12, fontWeight: 500,
                whiteSpace: 'nowrap', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 50,
              }}
            >
              <span style={{
                fontSize: 10,
                color: active ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
                marginBottom: 1,
              }}>{pillLabel(iso, todayIso)}</span>
              <span style={{ fontWeight: 600 }}>{best || '—'}</span>
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setCalendarOpen(o => !o)}
          style={{
            padding: '6px 12px', borderRadius: 14,
            border: `1px solid ${calendarOpen ? 'var(--g)' : 'var(--rule)'}`,
            background: calendarOpen ? 'var(--g)' : 'var(--white)',
            color: calendarOpen ? 'var(--white)' : 'var(--ink-2)',
            fontSize: 12, fontWeight: 500, cursor: 'pointer',
            display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 50,
          }}
        >
          <span style={{
            fontSize: 10,
            color: calendarOpen ? 'rgba(255,255,255,0.7)' : 'var(--ink-3)',
            marginBottom: 1,
          }}>PICK</span>
          <span>📅</span>
        </button>
      </div>
      {calendarOpen && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {monthPills.map(m => {
              const active = m === month;
              const d = new Date(`${m}-01T00:00:00`);
              const lbl = d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMonth(m)}
                  style={{
                    padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500,
                    background: active ? 'var(--g)' : 'transparent',
                    color: active ? 'var(--white)' : 'var(--ink-2)',
                    border: `1px solid ${active ? 'var(--g)' : 'var(--rule)'}`,
                    cursor: 'pointer',
                  }}
                >{lbl}</button>
              );
            })}
          </div>
          <CouponCalendar
            month={month}
            selectedDate={selectedDate}
            todayIso={todayIso}
            cellInfo={cellInfo}
            onSelect={(iso) => { onSelect(iso); setCalendarOpen(false); }}
          />
        </div>
      )}
    </div>
  );
}
