import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MuseumReservationBanner } from './MuseumReservationBanner';

describe('MuseumReservationBanner', () => {
  it('renders nothing when reservation is null', () => {
    const { container } = render(
      <MuseumReservationBanner reservation={null} attractionName="ICA Boston" variant="detail" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the one-line amber notice when reservation is required', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: 'https://icaboston.org/visit/tickets' }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(screen.getByText('Require Time Entry Reservation')).toBeInTheDocument();
  });

  it('is the same text in card variant — no CTA, no interaction', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: null }}
        attractionName="ICA Boston"
        variant="card"
      />
    );
    expect(screen.getByText('Require Time Entry Reservation')).toBeInTheDocument();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
