import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { act, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { BookingConfirmModal } from './BookingConfirmModal';
import type { Pass, Library } from '../data/types';
import type { CardPack } from '../stores/cardpack';

const mockPass: Pass = {
  library_id: 'wakefield',
  attraction_slug: 'zoo-boston',
  pass_form: 'digital_email',
  available_at_branches: 'all',
  coupon: {
    capacity: { kind: 'people', n: 4 },
    audience_policies: [
      { audience: 'Everyone', form: 'free', value: null, age_range: null, count: null },
    ],
  },
  restrictions: null,
  residency_restriction: { restricted: 'no', scope: null, source: null, evidence: null },
  source_url: 'https://example.com/book',
  availability: {},
};

const mockLibrary: Library = {
  id: 'wakefield',
  name: 'Wakefield Public Library',
  town: 'Wakefield',
  network: 'assabet',
  platform: 'assabet',
  card_page: 'https://wakefield.com/cards',
  card_eligibility: 'ma_resident',
  pass_pickup_default: 'unknown',
  resident_zips: ['01880'],
  address: null,
  geo: null,
};

const cardpackWithCard: CardPack = {
  zip: '01880',
  cards: {
    wakefield: { barcode: '21000012345678' },
  },
};

const cardpackWithoutCard: CardPack = {
  zip: '01880',
  cards: {},
};

describe('BookingConfirmModal', () => {
  it('renders nothing when pass is null', () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={null} library={null} cardpack={cardpackWithCard} onClose={onClose} />
    );
    expect(screen.queryByText('Get pass from')).not.toBeInTheDocument();
  });

  it('renders library name when pass is provided and modal is open', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );
    expect(await screen.findByText('Wakefield Public Library')).toBeInTheDocument();
  });

  it('shows barcode credential when card exists', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );
    expect(await screen.findByText('21000012345678')).toBeInTheDocument();
  });

  it('shows no-card warning when user has no card for this library', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithoutCard} onClose={onClose} />
    );
    expect(await screen.findByText(/You don't have a card from/)).toBeInTheDocument();
  });

  it('Copy-and-go button copies barcode and opens source_url (no in-app booking)', async () => {
    const onClose = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const windowOpen = vi.spyOn(window, 'open').mockImplementation(() => null);
    // Ensure fetch is not called — we only open the library page, never POST/submit in-app.
    const fetchSpy = vi.spyOn(window, 'fetch');

    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );

    const goBtn = await screen.findByRole('button', { name: /Copy card # and go/i });
    await act(async () => { fireEvent.click(goBtn); });

    expect(writeText).toHaveBeenCalledWith('21000012345678');
    // source_url is not an Assabet URL, so passUrlForDate returns it unchanged.
    expect(windowOpen).toHaveBeenCalledWith('https://example.com/book', '_blank', 'noopener,noreferrer');
    // Only one window.open call — no other navigations.
    expect(windowOpen).toHaveBeenCalledTimes(1);
    // No fetch/POST — we never submit a booking in-app.
    expect(fetchSpy).not.toHaveBeenCalled();

    windowOpen.mockRestore();
    fetchSpy.mockRestore();
  });

  it('fallback to library_id when library is null', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={null} cardpack={cardpackWithCard} onClose={onClose} />
    );
    // Falls back to pass.library_id as name
    expect(await screen.findByText('wakefield')).toBeInTheDocument();
  });

  it('shows timed-entry reminder with link when timedEntryUrl is provided', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal
        pass={mockPass}
        library={mockLibrary}
        cardpack={cardpackWithCard}
        onClose={onClose}
        timedEntryUrl="https://museum.example.com/timed-entry"
      />
    );
    expect(await screen.findByText(/此景点需到官网预约入场时段/)).toBeInTheDocument();
    const link = await screen.findByRole('link', { name: /预约 →/ });
    expect(link).toHaveAttribute('href', 'https://museum.example.com/timed-entry');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('does NOT show timed-entry reminder when timedEntryUrl is not provided', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );
    // Wait for the modal to fully render (library name present) then check reminder is absent.
    expect(await screen.findByText('Wakefield Public Library')).toBeInTheDocument();
    expect(screen.queryByText(/此景点需到官网预约入场时段/)).not.toBeInTheDocument();
  });
});
