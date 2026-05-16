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
  pass_type: 'digital',
  pass_type_raw: 'digital',
  discount: { class: 'free', label: 'Free', raw: 'Free' },
  policy: null,
  source_url: 'https://example.com/book',
  availability: null,
};

const mockLibrary: Library = {
  id: 'wakefield',
  name: 'Wakefield Public Library',
  town: 'Wakefield',
  network: 'assabet',
  platform: 'assabet',
  card_page: 'https://wakefield.com/cards',
  eligibility: 'Wakefield residents',
  supports_availability: true,
  address: null,
  geo: null,
};

const cardpackWithCard: CardPack = {
  zip: '01880',
  cards: {
    wakefield: { barcode: '21000012345678', lastName: 'Test', pin: '1234' },
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

  it('shows PIN credential when card has pin', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );
    expect(await screen.findByText('1234')).toBeInTheDocument();
  });

  it('shows no-card warning when user has no card for this library', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithoutCard} onClose={onClose} />
    );
    expect(await screen.findByText("You don't have a card for this library yet.")).toBeInTheDocument();
  });

  it('COPY button calls clipboard.writeText with barcode', async () => {
    const onClose = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );

    const copyBtns = await screen.findAllByText('COPY');
    await act(async () => { fireEvent.click(copyBtns[0]); });
    expect(writeText).toHaveBeenCalledWith('21000012345678');
  });

  it('go-to-library button calls window.open', async () => {
    const onClose = vi.fn();
    const windowOpen = vi.spyOn(window, 'open').mockImplementation(() => null);

    renderApp(
      <BookingConfirmModal pass={mockPass} library={mockLibrary} cardpack={cardpackWithCard} onClose={onClose} />
    );

    const goBtn = await screen.findByRole('button', { name: /Go to library website/i });
    fireEvent.click(goBtn);
    expect(windowOpen).toHaveBeenCalledWith('https://example.com/book', '_blank', 'noopener,noreferrer');
    windowOpen.mockRestore();
  });

  it('fallback to library_id when library is null', async () => {
    const onClose = vi.fn();
    renderApp(
      <BookingConfirmModal pass={mockPass} library={null} cardpack={cardpackWithCard} onClose={onClose} />
    );
    // Falls back to pass.library_id as name
    expect(await screen.findByText('wakefield')).toBeInTheDocument();
  });
});
