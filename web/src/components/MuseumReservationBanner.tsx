import type { MuseumReservation } from '../data/types';

interface Props {
  reservation: MuseumReservation | null;
  attractionName: string;
  /** Reserved for future per-context styling; the line itself is identical. */
  variant?: 'card' | 'detail';
}

/**
 * One-line amber notice rendered at the end of the attraction info block.
 *
 * Says exactly: "Require Time Entry Reservation". No CTA, no link — this is
 * a museum-side policy that applies to every visitor (with or without a pass),
 * so it's an informational hint, not a pass-related action prompt.
 */
export function MuseumReservationBanner({ reservation, variant = 'card' }: Props) {
  if (!reservation) return null;
  const url = reservation.url;
  // Reserve link only renders on the detail page. The list card is itself one
  // big <Link> tile (clickable through to /attractions/<slug>), so a nested
  // <a> inside would be invalid DOM (and would fight the parent click anyway).
  const showLink = variant === 'detail' && !!url;
  return (
    <p className="info-line" style={{ color: 'var(--au)' }}>
      <span className="info-icon" aria-hidden>
        <svg
          width={12} height={12} viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth={2}
          strokeLinecap="round" strokeLinejoin="round"
        >
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </span>
      <span>
        Timed-entry reservation required
        {showLink && (
          <>
            {' · '}
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ color: 'var(--au)', fontWeight: 600, textDecoration: 'none' }}
            >
              Reserve →
            </a>
          </>
        )}
      </span>
    </p>
  );
}
