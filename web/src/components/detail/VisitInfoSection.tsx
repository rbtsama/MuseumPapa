import { useState } from 'react';
import type { Attraction, Hours } from '../../data/types';
import { weeklyHoursList } from '../../lib/hours';

interface Props {
  attraction: Attraction;
}

function weeklySummary(hours: Hours | null | undefined): string {
  if (!hours) return 'Hours vary — see museum website';
  const vals = Object.values(hours);
  if (vals.every(v => !v || v === 'unknown')) return 'Hours vary — see museum website';

  const closedDays: string[] = [];
  const openDays: string[] = [];
  // Ordered Mon–Sun for display
  const order: Array<[string, keyof Hours]> = [
    ['Mon', 'monday'], ['Tue', 'tuesday'], ['Wed', 'wednesday'], ['Thu', 'thursday'],
    ['Fri', 'friday'], ['Sat', 'saturday'], ['Sun', 'sunday'],
  ];
  for (const [label, key] of order) {
    const v = hours[key];
    if (!v || v === 'unknown' || /closed/i.test(v)) closedDays.push(label);
    else openDays.push(label);
  }
  if (closedDays.length === 0) return 'open daily';
  if (closedDays.length === 7) return 'closed all week';
  if (closedDays.length <= 2) return `closed ${closedDays.join(', ')}`;
  return `open ${openDays.join(', ')}`;
}

function hasKnownHours(hours: Hours | null | undefined): boolean {
  if (!hours) return false;
  return Object.values(hours).some(v => v && v !== 'unknown');
}

function formatAddress(address: Attraction['address']): string | null {
  if (!address) return null;
  const parts = [
    address.street,
    address.city,
    address.state && address.zip ? `${address.state} ${address.zip}` : (address.state ?? address.zip),
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(', ') : null;
}

export function VisitInfoSection({ attraction }: Props) {
  const [showAll, setShowAll] = useState(false);
  const hoursObj = attraction.hours ?? null;
  const hasHours = hasKnownHours(hoursObj);
  const addressStr = formatAddress(attraction.address ?? null);

  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--ink-3)',
        textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>Visit info</h3>

      <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '4px 0' }}>
        <b>Hours this week</b>{' '}
        <span style={{ color: 'var(--ink-3)' }}>· {weeklySummary(hoursObj)}</span>
        {hasHours && (
          <button
            type="button"
            onClick={() => setShowAll(s => !s)}
            style={{
              background: 'transparent', border: 'none', padding: 0,
              color: 'var(--g)', fontWeight: 500, fontSize: 11, marginLeft: 6, cursor: 'pointer',
            }}
          >{showAll ? 'Hide' : 'See all →'}</button>
        )}
      </div>

      {showAll && hasHours && hoursObj && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', margin: '8px 0' }}>
          {weeklyHoursList(hoursObj).map(row => {
            const isClosed = row.value.toLowerCase() === 'closed';
            return (
              <div key={row.key} style={{ display: 'flex', gap: 6, fontSize: 11 }}>
                <span style={{
                  color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.04em', width: 32,
                }}>
                  {row.label}
                </span>
                <span style={{ color: isClosed ? 'var(--rd)' : 'var(--ink-2)', fontWeight: 500 }}>
                  {row.value}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {addressStr && (
        <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '8px 0' }}>
          <b>Address</b>
          <div style={{ color: 'var(--ink-3)', marginTop: 2 }}>{addressStr}</div>
        </div>
      )}

      <div style={{ fontSize: 12, color: 'var(--ink-2)', margin: '8px 0', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {attraction.phone && (
          <span>📞 <a href={`tel:${attraction.phone.replace(/[^\d+]/g, '')}`} style={{ color: 'var(--g)' }}>{attraction.phone}</a></span>
        )}
        {attraction.website && (
          <span>🌐 <a href={attraction.website} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--g)' }}>
            {attraction.website.replace(/^https?:\/\//, '').replace(/\/$/, '')} →
          </a></span>
        )}
      </div>
    </section>
  );
}
