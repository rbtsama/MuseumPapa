import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent, waitFor, act } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { MyLibraryCards } from './MyLibraryCards';
import { useCardpack } from '../stores/cardpack';
import { useAuth } from '../auth/store';
import * as distance from '../lib/distance';

vi.mock('../lib/distance', () => ({
  geocodeZip: vi.fn(),
  haversineMiles: vi.fn().mockReturnValue(5),
}));

const geocodeMock = distance.geocodeZip as ReturnType<typeof vi.fn>;

const FAKE_USER = { username: 'testuser', displayName: 'Test User', persona: 'empty' as const };

beforeEach(() => {
  useCardpack.setState({ pack: { zip: '', cards: {} }, username: null });
  useAuth.setState({ currentUser: FAKE_USER });
  geocodeMock.mockReset();
});

describe('MyLibraryCards page', () => {
  it('shows sign-in prompt when no user is logged in', () => {
    useAuth.setState({ currentUser: null });
    renderApp(<MyLibraryCards />);
    expect(screen.getByText(/Sign in to manage your cards/i)).toBeInTheDocument();
  });

  it('renders a ZIP code input when signed in', () => {
    renderApp(<MyLibraryCards />);
    expect(screen.getByRole('textbox', { name: 'Your ZIP code' })).toBeInTheDocument();
  });

  it('(a) saving ZIP "01880" persists to cardpack store', async () => {
    geocodeMock.mockResolvedValue({ lat: 42.5, lon: -71.0 });
    renderApp(<MyLibraryCards />);
    const input = screen.getByRole('textbox', { name: 'Your ZIP code' });
    fireEvent.change(input, { target: { value: '01880' } });
    fireEvent.blur(input);
    await waitFor(() => expect(useCardpack.getState().pack.zip).toBe('01880'));
  });

  it('(b) shows BPL eCard warning when BPL card is held', async () => {
    renderApp(<MyLibraryCards />);
    // After mount, the useEffect/load fires with username=null → resets to EMPTY.
    // Now forcibly inject a BPL card into the live store.
    act(() => {
      useCardpack.setState({
        pack: { zip: '', cards: { bpl: { barcode: '21000000000003' } } },
        username: 'testuser',
      });
    });
    const warning = await screen.findByRole('alert');
    expect(warning).toBeInTheDocument();
    expect(warning).toHaveTextContent(/physical/i);
  });

  it('(b) does NOT show BPL eCard warning when no BPL card is held', async () => {
    renderApp(<MyLibraryCards />);
    // Ensure no BPL card in state
    act(() => {
      useCardpack.setState({
        pack: { zip: '', cards: {} },
        username: 'testuser',
      });
    });
    // Wait a tick for state to settle
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull();
    });
  });

  it('(b) BPL warning disappears after BPL card is removed from state', async () => {
    renderApp(<MyLibraryCards />);

    // Set BPL card held
    act(() => {
      useCardpack.setState({
        pack: { zip: '', cards: { bpl: { barcode: '' } } },
        username: 'testuser',
      });
    });
    expect(await screen.findByRole('alert')).toBeInTheDocument();

    // Remove BPL card
    act(() => {
      useCardpack.setState({
        pack: { zip: '', cards: {} },
        username: 'testuser',
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull();
    });
  });
});
