import { create } from 'zustand';
import users from './users.json';
import { lsGet, lsSet, lsRemove } from '../lib/localStorage';

export interface User {
  username: string;
  displayName: string;
  persona: 'heavy' | 'light' | 'empty';
}

interface AuthState {
  currentUser: User | null;
  signIn: (username: string, password: string) => { ok: true } | { ok: false; error: string };
  signOut: () => void;
  loadFromStorage: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  currentUser: null,

  signIn: (username, password) => {
    const found = users.users.find(
      u => u.username === username && u.password === password
    );
    if (!found) {
      return { ok: false, error: 'Invalid username or password' };
    }
    const user: User = {
      username: found.username,
      displayName: found.displayName,
      persona: found.persona as User['persona'],
    };
    lsSet('session', user);
    set({ currentUser: user });
    return { ok: true };
  },

  signOut: () => {
    lsRemove('session');
    set({ currentUser: null });
  },

  loadFromStorage: () => {
    const session = lsGet<User | null>('session', null);
    if (session) set({ currentUser: session });
  },
}));
