import type { Attraction } from '../../data/types';
import { MuseumReservationBanner } from '../MuseumReservationBanner';
import { hoursDisplay, isClosedOn } from '../../lib/hours';
import { formatOriginalAdult } from '../../lib/originalPrice';

interface Props {
  attraction: Attraction;
  todayIso: string;
}

function formatHeading(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

export function TodayFactsCard({ attraction, todayIso }: Props) {
  const closed = isClosedOn(attraction, todayIso);
  const hours = hoursDisplay(attraction, todayIso);
  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--ink-3)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}>
        Today · {formatHeading(todayIso)}
      </h3>
      <div style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 6, fontWeight: 500 }}>
        {closed ? (
          <span style={{ color: 'var(--rd)', fontWeight: 600 }}>● Closed today</span>
        ) : (
          <>
            <span style={{ color: 'var(--g)', fontWeight: 600 }}>● Open now</span>
            {hours && <> · {hours.value}</>}
          </>
        )}
      </div>
      <div
        className="font-serif"
        style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink-2)' }}
      >
        {formatOriginalAdult(attraction.original_price)}
      </div>
      {attraction.museum_reservation && (
        <div style={{ marginTop: 8 }}>
          <MuseumReservationBanner
            reservation={attraction.museum_reservation}
            attractionName={attraction.museum_name}
            variant="detail"
          />
        </div>
      )}
    </section>
  );
}
