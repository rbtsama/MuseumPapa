import { describe, it, expect, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { FavoriteButton } from './FavoriteButton';
import { useFavorites } from '../stores/favorites';

beforeEach(() => {
  useFavorites.setState({ slugs: new Set() });
});

describe('FavoriteButton', () => {
  it('renders as not-favorited by default', () => {
    renderApp(<FavoriteButton slug="test-attraction" />);
    const btn = screen.getByRole('button');
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    expect(btn).toHaveAttribute('aria-label', 'Add to favorites');
  });

  it('clicking toggles to favorited', () => {
    renderApp(<FavoriteButton slug="test-attraction" />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(btn).toHaveAttribute('aria-label', 'Remove from favorites');
  });

  it('clicking twice toggles back to not-favorited', () => {
    renderApp(<FavoriteButton slug="test-attraction" />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('overlay variant renders correctly', () => {
    renderApp(<FavoriteButton slug="test-attraction" variant="overlay" />);
    const btn = screen.getByRole('button');
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('reflects pre-existing favorites state', () => {
    useFavorites.setState({ slugs: new Set(['test-attraction']) });
    renderApp(<FavoriteButton slug="test-attraction" />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'true');
    expect(btn).toHaveAttribute('aria-label', 'Remove from favorites');
  });
});
