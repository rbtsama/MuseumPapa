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

  it('renders nothing when required is "none"', () => {
    const { container } = render(
      <MuseumReservationBanner
        reservation={{ required: 'none', booking_url: null }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when required is "walk_in_ok"', () => {
    const { container } = render(
      <MuseumReservationBanner
        reservation={{ required: 'walk_in_ok', booking_url: null }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the one-line amber notice when required is "timed_entry" (detail variant shows link)', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: 'timed_entry', booking_url: 'https://icaboston.org/visit/tickets' }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(screen.getByText(/Timed-entry reservation required/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Reserve/ })).toHaveAttribute(
      'href',
      'https://icaboston.org/visit/tickets',
    );
  });

  it('is the same text in card variant — no CTA link even when booking_url present', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: 'timed_entry', booking_url: 'https://icaboston.org/visit/tickets' }}
        attractionName="ICA Boston"
        variant="card"
      />
    );
    expect(screen.getByText('Timed-entry reservation required')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('renders notice without a link when booking_url is null (detail variant)', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: 'timed_entry', booking_url: null }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(screen.getByText('Timed-entry reservation required')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
