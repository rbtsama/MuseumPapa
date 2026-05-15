import { create } from 'zustand';
import { lsGetUser, lsSetUser } from '../lib/localStorage';

interface FavoritesState {
  username: string | null;
  slugs: Set<string>;
  load: (username: string | null) => void;
  toggle: (slug: string) => void;
  isFavorite: (slug: string) => boolean;
}

export const useFavorites = create<FavoritesState>((set, get) => ({
  username: null,
  slugs: new Set(),

  load: (username) => {
    const arr = lsGetUser<string[]>(username, 'favorites', []);
    set({ username, slugs: new Set(arr) });
  },

  toggle: (slug) => {
    const { username, slugs } = get();
    const next = new Set(slugs);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    lsSetUser(username, 'favorites', Array.from(next));
    set({ slugs: next });
  },

  isFavorite: (slug) => get().slugs.has(slug),
}));
