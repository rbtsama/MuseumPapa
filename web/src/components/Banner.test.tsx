import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { Banner } from './Banner';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';

describe('Banner', () => {
  beforeEach(() => {
    useAuth.setState({ currentUser: null });
    useCardpack.setState({ pack: { zip: '', cards: {} } });
  });

  it('guest with no cards: shows Sign in CTA', () => {
    const onSignInClick = vi.fn();
    renderApp(<Banner onSignInClick={onSignInClick} />);
    expect(screen.getByText(/Add your library pass/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in/i)).toBeInTheDocument();
  });

  it('guest Sign in click fires callback', () => {
    const onSignInClick = vi.fn();
    renderApp(<Banner onSignInClick={onSignInClick} />);
    fireEvent.click(screen.getByText(/Sign in/i));
    expect(onSignInClick).toHaveBeenCalledTimes(1);
  });

  it('signed-in user with no cards: shows Set up CTA linking to settings', () => {
    useAuth.setState({
      currentUser: { username: 'u', displayName: 'U', persona: 'empty' },
    });
    renderApp(<Banner onSignInClick={() => {}} />);
    expect(screen.getByText(/Add your library passes/i)).toBeInTheDocument();
    const link = screen.getByText(/Manage passes/i);
    expect(link.closest('a')).toHaveAttribute('href', '/settings/passes');
  });

  it('signed-in user WITH cards: renders nothing', () => {
    useAuth.setState({
      currentUser: { username: 'u', displayName: 'U', persona: 'heavy' },
    });
    useCardpack.setState({
      pack: { zip: '01880', cards: { wakefield: { barcode: '123', pin: '' } } },
    });
    renderApp(<Banner onSignInClick={() => {}} />);
    expect(screen.queryByText(/Add your library passes/i)).not.toBeInTheDocument();
  });
});
