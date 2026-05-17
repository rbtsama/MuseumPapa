import type { MuseumReservation } from '../data/types';

interface Props {
  reservation: MuseumReservation | null;
  attractionName: string;
  variant: 'card' | 'detail';
}

export function MuseumReservationBanner({ reservation, attractionName, variant }: Props) {
  if (!reservation) return null;
  const url = reservation.url;
  const handleClick = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  };
  const handleKey = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ' ') && url) {
      e.preventDefault();
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  const interactive = url != null;
  const baseStyle: React.CSSProperties = {
    background: 'var(--or-pale)',
    borderLeft: '3px solid var(--or)',
    color: 'var(--or)',
    cursor: interactive ? 'pointer' : 'default',
    userSelect: 'none',
  };

  if (variant === 'card') {
    return (
      <div
        role={interactive ? 'button' : undefined}
        tabIndex={interactive ? 0 : -1}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleClick(); }}
        onKeyDown={(e) => { e.stopPropagation(); handleKey(e); }}
        aria-label={`Reserve admission at ${attractionName} first`}
        className="flex items-center justify-between"
        style={{ ...baseStyle, fontSize: 12, padding: '6px 10px', lineHeight: 1.3, fontWeight: 500 }}
      >
        <span>Reserve admission at the museum first</span>
        <span aria-hidden style={{ fontSize: 16, marginLeft: 8 }}>›</span>
      </div>
    );
  }

  return (
    <div
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : -1}
      onClick={handleClick}
      onKeyDown={handleKey}
      aria-label={`Reserve admission at ${attractionName} first`}
      className="flex items-center justify-between"
      style={{ ...baseStyle, fontSize: 13, padding: '10px 14px', lineHeight: 1.4, fontWeight: 500, borderRadius: 4 }}
    >
      <span>
        Reserve a timed entry at <b>{attractionName}</b> before using any pass below.
      </span>
      <span aria-hidden style={{ fontSize: 20, marginLeft: 12 }}>›</span>
    </div>
  );
}
