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
export function MuseumReservationBanner({ reservation }: Props) {
  if (!reservation) return null;
  return (
    <p
      className="mt-0.5"
      style={{
        fontSize: 12,
        color: 'var(--au)',
        lineHeight: 1.35,
      }}
    >
      <span className="info-icon" aria-hidden>⚠</span>
      Require Time Entry Reservation
    </p>
  );
}
