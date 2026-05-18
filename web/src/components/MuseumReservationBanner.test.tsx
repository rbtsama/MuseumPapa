import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MuseumReservationBanner } from './MuseumReservationBanner';

describe('MuseumReservationBanner', () => {
  beforeEach(() => {
    vi.stubGlobal('open', vi.fn());
  });

  it('renders nothing when reservation is null', () => {
    const { container } = render(
      <MuseumReservationBanner reservation={null} attractionName="ICA Boston" variant="detail" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the detail-page text with the museum name', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: 'https://icaboston.org/visit/tickets' }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(screen.getByText(/ICA Boston requires a timed-entry reservation/)).toBeInTheDocument();
    expect(screen.getByText(/Reserve/)).toBeInTheDocument();
  });

  it('renders the card-variant single-line text', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: 'https://icaboston.org' }}
        attractionName="ICA Boston"
        variant="card"
      />
    );
    expect(screen.getByText('Museum requires timed-entry reservation')).toBeInTheDocument();
  });

  it('opens the museum URL in a new tab on click', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: 'https://icaboston.org/visit/tickets' }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    fireEvent.click(screen.getByRole('button'));
    expect(window.open).toHaveBeenCalledWith(
      'https://icaboston.org/visit/tickets', '_blank', 'noopener,noreferrer'
    );
  });

  it('is not clickable when the URL is null', () => {
    render(
      <MuseumReservationBanner
        reservation={{ required: true, url: null }}
        attractionName="ICA Boston"
        variant="detail"
      />
    );
    expect(screen.queryByRole('button')).toBeNull();
  });
});
