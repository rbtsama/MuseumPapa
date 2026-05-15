import { describe, it, expect, beforeEach } from 'vitest';
import { useFavorites } from './favorites';

describe('favorites store', () => {
  beforeEach(() => {
    localStorage.clear();
    useFavorites.setState({ username: null, slugs: new Set() });
  });

  it('loads empty for new user', () => {
    useFavorites.getState().load('alex');
    expect(useFavorites.getState().slugs.size).toBe(0);
  });

  it('toggle adds then removes', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    expect(useFavorites.getState().isFavorite('mos')).toBe(true);
    useFavorites.getState().toggle('mos');
    expect(useFavorites.getState().isFavorite('mos')).toBe(false);
  });

  it('persists across reload', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    useFavorites.getState().toggle('neaq');
    useFavorites.setState({ username: null, slugs: new Set() });
    useFavorites.getState().load('alex');
    expect(useFavorites.getState().slugs).toEqual(new Set(['mos', 'neaq']));
  });

  it('per-user separation', () => {
    useFavorites.getState().load('alex');
    useFavorites.getState().toggle('mos');
    useFavorites.getState().load('rbt');
    expect(useFavorites.getState().isFavorite('mos')).toBe(false);
  });
});
