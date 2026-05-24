import type { Reservation } from '../data/types';
import { TriangleExclamationIcon } from './icons';

interface Props {
  reservation: Reservation | null | undefined;
  attractionName: string;
  /** Reserved for future per-context styling; the line itself is identical. */
  variant?: 'card' | 'detail';
}

/**
 * One-line amber notice rendered at the end of the attraction info block.
 *
 * Shows only when reservation.required === 'timed_entry' — these attractions
 * need advance booking before visiting. walk_in_ok / none → no banner.
 *
 * Says exactly: "Timed-entry reservation required". No CTA, no link — this is
 * a museum-side policy that applies to every visitor (with or without a pass),
 * so it's an informational hint, not a pass-related action prompt.
 */
export function MuseumReservationBanner({ reservation, variant = 'card' }: Props) {
  if (!reservation || reservation.required !== 'timed_entry') return null;
  const url = reservation.booking_url;
  // Reserve link only renders on the detail page. The list card is itself one
  // big <Link> tile (clickable through to /attractions/<slug>), so a nested
  // <a> inside would be invalid DOM (and would fight the parent click anyway).
  const showLink = variant === 'detail' && !!url;
  return (
    <p className="info-line" style={{ color: 'var(--au)' }}>
      <span className="info-icon" aria-hidden>
        <TriangleExclamationIcon />
      </span>
      <span>
        Timed-entry reservation required
        {showLink && (
          <>
            {' · '}
            <a
              href={url!}
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
