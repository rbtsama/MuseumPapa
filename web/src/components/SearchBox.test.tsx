import { describe, it, expect, vi } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { SearchBox } from './SearchBox';

describe('SearchBox', () => {
  it('renders input with correct placeholder', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="" onChange={onChange} />);
    expect(screen.getByRole('searchbox', { name: 'Search attractions' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search attractions')).toBeInTheDocument();
  });

  it('calls onChange when user types', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="" onChange={onChange} />);
    const input = screen.getByRole('searchbox');
    fireEvent.change(input, { target: { value: 'zoo' } });
    expect(onChange).toHaveBeenCalledWith('zoo');
  });

  it('shows clear button when value is non-empty', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="aquarium" onChange={onChange} />);
    expect(screen.getByRole('button', { name: 'Clear search' })).toBeInTheDocument();
  });

  it('does not show clear button when value is empty', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="" onChange={onChange} />);
    expect(screen.queryByRole('button', { name: 'Clear search' })).not.toBeInTheDocument();
  });

  it('clicking clear button calls onChange with empty string', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="aquarium" onChange={onChange} />);
    const clearBtn = screen.getByRole('button', { name: 'Clear search' });
    fireEvent.click(clearBtn);
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('supports custom placeholder', () => {
    const onChange = vi.fn();
    renderApp(<SearchBox value="" onChange={onChange} placeholder="Search museums" />);
    expect(screen.getByPlaceholderText('Search museums')).toBeInTheDocument();
  });
});
