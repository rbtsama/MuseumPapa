import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { CategoryChips } from './CategoryChips';
import type { Attraction } from '../data/types';

function makeAttraction(slug: string, categories: string[]): Attraction {
  return {
    slug,
    museum_name: slug,
    address: '123 Main St, Boston, MA 02101',
    website: 'https://example.com',
    phone: null,
    description: null,
    categories,
    sources: [],
    original_price: null,
    hero_image: null,
    geo: null,
    hours: null,
  };
}

const attractions: Attraction[] = [
  makeAttraction('zoo', ['Animals', 'Family']),
  makeAttraction('museum', ['History', 'Family']),
  makeAttraction('aquarium', ['Ocean', 'Animals']),
];

describe('CategoryChips', () => {
  it('renders "All" chip with total count', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="all"
        onChange={onChange}
        favoritesCount={0}
      />
    );
    // All chip should show total count = 3
    const allBtn = screen.getByRole('button', { name: /All/ });
    expect(allBtn).toBeInTheDocument();
    expect(allBtn).toHaveTextContent('3');
  });

  it('renders Favorites chip', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="all"
        onChange={onChange}
        favoritesCount={2}
      />
    );
    const favBtn = screen.getByRole('button', { name: /Favorites/ });
    expect(favBtn).toBeInTheDocument();
    expect(favBtn).toHaveTextContent('2');
  });

  it('renders category chips from attraction data', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="all"
        onChange={onChange}
        favoritesCount={0}
      />
    );
    // Family appears in 2 attractions, Animals in 2 — both should be chips
    expect(screen.getByRole('button', { name: /Family/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Animals/ })).toBeInTheDocument();
  });

  it('clicking a category calls onChange with that category', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="all"
        onChange={onChange}
        favoritesCount={0}
      />
    );
    const familyBtn = screen.getByRole('button', { name: /Family/ });
    fireEvent.click(familyBtn);
    expect(onChange).toHaveBeenCalledWith('Family');
  });

  it('clicking All chip calls onChange with "all"', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="Family"
        onChange={onChange}
        favoritesCount={0}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /All/ }));
    expect(onChange).toHaveBeenCalledWith('all');
  });

  it('clicking Favorites chip calls onChange with "favorites"', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips
        attractions={attractions}
        value="all"
        onChange={onChange}
        favoritesCount={1}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /Favorites/ }));
    expect(onChange).toHaveBeenCalledWith('favorites');
  });
});
