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
  // Light tinted background gives it an "interactive strip" feel without the
  // heavy borders / left rule that made it look like a hard alert; sits as
  // its own row between the attraction info and the pass list.
  const baseStyle: React.CSSProperties = {
    color: 'var(--or)',
    background: 'var(--or-pale)',
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
        style={{ ...baseStyle, fontSize: 12, padding: '8px 12px', lineHeight: 1.3,
                 borderBottom: '1px solid var(--rule)' }}
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
      style={{ ...baseStyle, fontSize: 13, padding: '10px 14px', lineHeight: 1.4, borderRadius: 4 }}
    >
      <span>
        This pass requires a museum reservation at {attractionName} before use.
      </span>
      {cta}
    </div>
  );
}
