import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { ZipPill } from './ZipPill';
import { useCardpack } from '../stores/cardpack';

// Mock geocodeZip to avoid network calls in tests
vi.mock('../lib/distance', () => ({
  geocodeZip: vi.fn().mockResolvedValue({ lat: 42.5, lon: -71.0 }),
  haversineMiles: vi.fn().mockReturnValue(5),
}));

beforeEach(() => {
  useCardpack.setState({ pack: { zip: '', cards: {} } });
});

describe('ZipPill', () => {
  it('renders input with "your location" label', () => {
    renderApp(<ZipPill />);
    expect(screen.getByText('your location')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Your ZIP code' })).toBeInTheDocument();
  });

  it('accepts digits only and strips non-digits', () => {
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '01880' } });
    expect(input).toHaveValue('01880');
  });

  it('shows invalid state (aria-invalid) when fewer than 5 digits typed', () => {
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '018' } });
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('saves ZIP on blur with valid 5-digit value', () => {
    renderApp(<ZipPill />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '01880' } });
    fireEvent.blur(input);
    expect(useCardpack.getState().pack.zip).toBe('01880');
  });
});
