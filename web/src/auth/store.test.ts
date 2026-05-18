import { describe, it, expect, beforeEach } from 'vitest';
import { useAuth } from './store';

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuth.setState({ currentUser: null });
  });

  it('rejects unknown username', () => {
    const result = useAuth.getState().signIn('nobody', 'wrong');
    expect(result.ok).toBe(false);
    expect(useAuth.getState().currentUser).toBeNull();
  });

  it('rejects wrong password', () => {
    const result = useAuth.getState().signIn('alex', 'wrong');
    expect(result.ok).toBe(false);
  });

  it('signs in alex with persona=heavy', () => {
    const result = useAuth.getState().signIn('alex', 'alex');
    expect(result.ok).toBe(true);
    const user = useAuth.getState().currentUser;
    expect(user?.username).toBe('alex');
    expect(user?.persona).toBe('heavy');
  });

  it('signs in rbt with persona=light', () => {
    useAuth.getState().signIn('rbt', 'rbt');
    expect(useAuth.getState().currentUser?.persona).toBe('light');
  });

  it('signs in admin with persona=empty', () => {
    useAuth.getState().signIn('admin', 'admin');
    expect(useAuth.getState().currentUser?.persona).toBe('empty');
  });

  it('persists session to localStorage', () => {
    useAuth.getState().signIn('alex', 'alex');
    expect(localStorage.getItem('museumpass-ma.session')).toBeTruthy();
  });

  it('loadFromStorage restores session', () => {
    useAuth.getState().signIn('alex', 'alex');
    useAuth.setState({ currentUser: null });
    useAuth.getState().loadFromStorage();
    expect(useAuth.getState().currentUser?.username).toBe('alex');
  });

  it('signOut clears state and localStorage', () => {
    useAuth.getState().signIn('alex', 'alex');
    useAuth.getState().signOut();
    expect(useAuth.getState().currentUser).toBeNull();
    expect(localStorage.getItem('museumpass-ma.session')).toBeNull();
  });

  // signUp integration tests
  it('signUp rejects username shorter than 2 chars', () => {
    const result = useAuth.getState().signUp('x', 'password123');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/2 char/i);
    expect(useAuth.getState().currentUser).toBeNull();
  });

  it('signUp rejects password shorter than 4 chars', () => {
    const result = useAuth.getState().signUp('newuser', 'abc');
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/4 char/i);
    expect(useAuth.getState().currentUser).toBeNull();
  });

  it('signUp rejects duplicate of seeded users (alex, rbt, admin)', () => {
    for (const username of ['alex', 'rbt', 'admin']) {
      const result = useAuth.getState().signUp(username, 'newpassword');
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.error).toMatch(/taken/i);
      expect(useAuth.getState().currentUser).toBeNull();
    }
  });

  it('signUp succeeds, persists to localStorage, and signs in the new user', () => {
    const result = useAuth.getState().signUp('newbie', 'pass1234', 'Newbie User');
    expect(result.ok).toBe(true);
    const user = useAuth.getState().currentUser;
    expect(user?.username).toBe('newbie');
    expect(user?.displayName).toBe('Newbie User');
    expect(user?.persona).toBe('empty');
    expect(localStorage.getItem('museumpass-ma.session')).toBeTruthy();
    expect(localStorage.getItem('museumpass-ma.registered_users')).toBeTruthy();
  });

  it('after signUp + signOut + signIn with same credentials, session restores', () => {
    useAuth.getState().signUp('relogger', 'mypassword');
    useAuth.getState().signOut();
    expect(useAuth.getState().currentUser).toBeNull();
    const result = useAuth.getState().signIn('relogger', 'mypassword');
    expect(result.ok).toBe(true);
    expect(useAuth.getState().currentUser?.username).toBe('relogger');
  });
});
