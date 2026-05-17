import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { ZipPill } from './ZipPill';
import { useCardpack } from '../stores/cardpack';
import * as distance from '../lib/distance';

vi.mock('../lib/distance', () => ({
  geocodeZip: vi.fn(),
  haversineMiles: vi.fn().mockReturnValue(5),
}));

const geocodeMock = distance.geocodeZip as ReturnType<typeof vi.fn>;

beforeEach(() => {
  useCardpack.setState({ pack: { zip: '', cards: {} } });
  geocodeMock.mockReset();
});

describe('ZipPill', () => {
  it('renders the input with a ZIP code label', () => {
    renderApp(<ZipPill />);
    expect(screen.getByText('ZIP code')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Your ZIP code' })).toBeInTheDocument();
  });

  it('strips non-digit characters from input', () => {
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: 'abc01880xyz' } });
    expect(input).toHaveValue('01880');
  });

  it('saves a valid 5-digit ZIP on blur', async () => {
    geocodeMock.mockResolvedValue({ lat: 42.5, lon: -71.0 });
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '01880' } });
    fireEvent.blur(input);
    await waitFor(() => expect(useCardpack.getState().pack.zip).toBe('01880'));
  });

  it('does NOT save an incomplete ZIP and shows a hint', () => {
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '018' } });
    fireEvent.blur(input);
    expect(useCardpack.getState().pack.zip).toBe('');
    expect(screen.getByText(/Need 5 digits/)).toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('does NOT save a 5-digit ZIP that fails geocoding and shows a hint', async () => {
    geocodeMock.mockResolvedValue(null);
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '99999' } });
    fireEvent.blur(input);
    await waitFor(() => expect(screen.getByText(/Not a valid US ZIP/)).toBeInTheDocument());
    expect(useCardpack.getState().pack.zip).toBe('');
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('clearing the field saves empty string (resets the ZIP)', async () => {
    useCardpack.setState({ pack: { zip: '01880', cards: {} } });
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.blur(input);
    await waitFor(() => expect(useCardpack.getState().pack.zip).toBe(''));
  });
});
