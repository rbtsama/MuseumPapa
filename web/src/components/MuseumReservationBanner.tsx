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
    color: 'var(--or)',
    cursor: interactive ? 'pointer' : 'default',
    userSelect: 'none',
  };

  const cta = (
    <span className="flex items-center flex-shrink-0">
      Reserve <span aria-hidden style={{ marginLeft: 4 }}>›</span>
    </span>
  );

  if (variant === 'card') {
    return (
      <div
        role={interactive ? 'button' : undefined}
        tabIndex={interactive ? 0 : -1}
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleClick(); }}
        onKeyDown={(e) => { e.stopPropagation(); handleKey(e); }}
        aria-label={`This pass requires a museum reservation at ${attractionName}`}
        className="flex items-center justify-between gap-3"
        style={{ ...baseStyle, fontSize: 12, padding: '4px 12px', lineHeight: 1.3 }}
      >
        <span>Pass requires a museum reservation</span>
        {cta}
      </div>
    );
  }

  return (
    <div
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : -1}
      onClick={handleClick}
      onKeyDown={handleKey}
      aria-label={`This pass requires a museum reservation at ${attractionName}`}
      className="flex items-center justify-between gap-3"
      style={{ ...baseStyle, fontSize: 13, padding: '4px 0', lineHeight: 1.4 }}
    >
      <span>
        This pass requires a museum reservation at {attractionName} before use.
      </span>
      {cta}
    </div>
  );
}
