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
});
