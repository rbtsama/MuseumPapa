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
    museum_reservation: null,
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
      <CategoryChips attractions={attractions} value="all" onChange={onChange} />
    );
    const allBtn = screen.getByRole('button', { name: /All/ });
    expect(allBtn).toBeInTheDocument();
    expect(allBtn).toHaveTextContent('3');
  });

  it('renders category chips from attraction data', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips attractions={attractions} value="all" onChange={onChange} />
    );
    expect(screen.getByRole('button', { name: /Family/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Animals/ })).toBeInTheDocument();
  });

  it('clicking a category calls onChange with that category', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips attractions={attractions} value="all" onChange={onChange} />
    );
    fireEvent.click(screen.getByRole('button', { name: /Family/ }));
    expect(onChange).toHaveBeenCalledWith('Family');
  });

  it('clicking All chip calls onChange with "all"', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips attractions={attractions} value="Family" onChange={onChange} />
    );
    fireEvent.click(screen.getByRole('button', { name: /All/ }));
    expect(onChange).toHaveBeenCalledWith('all');
  });

  it('no longer renders a Favorites chip (extracted to FavoritesToggle)', () => {
    const onChange = vi.fn();
    renderApp(
      <CategoryChips attractions={attractions} value="all" onChange={onChange} />
    );
    expect(screen.queryByRole('button', { name: /Favorites/ })).toBeNull();
  });
});
