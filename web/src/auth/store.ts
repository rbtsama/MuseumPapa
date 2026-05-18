import { create } from 'zustand';
import users from './users.json';
import { lsGet, lsSet, lsRemove } from '../lib/localStorage';

export interface User {
  username: string;
  displayName: string;
  persona: 'heavy' | 'light' | 'empty';
}

interface StoredAccount {
  username: string;
  password: string;
  displayName: string;
  persona: User['persona'];
}

interface AuthState {
  currentUser: User | null;
  signIn: (username: string, password: string) => { ok: true } | { ok: false; error: string };
  signUp: (username: string, password: string, displayName?: string)
    => { ok: true } | { ok: false; error: string };
  signOut: () => void;
  loadFromStorage: () => void;
}

const REGISTERED_KEY = 'registered_users';

function loadRegistered(): StoredAccount[] {
  return lsGet<StoredAccount[]>(REGISTERED_KEY, []);
}

function findAccount(username: string, password: string): StoredAccount | undefined {
  const seeded = users.users.find(u => u.username === username && u.password === password);
  if (seeded) return seeded as StoredAccount;
  return loadRegistered().find(u => u.username === username && u.password === password);
}

function usernameTaken(username: string): boolean {
  if (users.users.some(u => u.username === username)) return true;
  return loadRegistered().some(u => u.username === username);
}

export const useAuth = create<AuthState>((set) => ({
  currentUser: null,

  signIn: (username, password) => {
    const found = findAccount(username, password);
    if (!found) return { ok: false, error: 'Invalid username or password' };
    const user: User = {
      username: found.username,
      displayName: found.displayName,
      persona: found.persona,
    };
    lsSet('session', user);
    set({ currentUser: user });
    return { ok: true };
  },

  signUp: (username, password, displayName) => {
    const uname = username.trim();
    const pw = password;
    if (uname.length < 2) return { ok: false, error: 'Username must be at least 2 characters' };
    if (pw.length < 4) return { ok: false, error: 'Password must be at least 4 characters' };
    if (usernameTaken(uname)) return { ok: false, error: 'Username already taken' };
    const account: StoredAccount = {
      username: uname,
      password: pw,
      displayName: displayName?.trim() || uname,
      persona: 'empty',
    };
    const all = loadRegistered();
    all.push(account);
    lsSet(REGISTERED_KEY, all);
    const user: User = {
      username: account.username,
      displayName: account.displayName,
      persona: account.persona,
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
