import { describe, it, expect, beforeEach } from 'vitest';
import { useCardpack } from './cardpack';

describe('cardpack store', () => {
  beforeEach(() => {
    localStorage.clear();
    useCardpack.setState({ username: null, pack: { zip: '', cards: {} } });
  });

  it('loads empty pack for guest', () => {
    useCardpack.getState().load(null);
    expect(useCardpack.getState().pack.cards).toEqual({});
    expect(useCardpack.getState().pack.zip).toBe('');
  });

  it('seeds alex with 5 cards on first load', () => {
    useCardpack.getState().load('alex');
    const p = useCardpack.getState().pack;
    expect(Object.keys(p.cards).length).toBe(5);
    expect(p.cards.wakefield.barcode).toBeTruthy();
    expect(p.zip).toBe('01880');
  });

  it('seeds rbt with 1 card on first load', () => {
    useCardpack.getState().load('rbt');
    expect(Object.keys(useCardpack.getState().pack.cards).length).toBe(1);
  });

  it('seeds admin with 0 cards', () => {
    useCardpack.getState().load('admin');
    expect(Object.keys(useCardpack.getState().pack.cards)).toEqual([]);
    expect(useCardpack.getState().pack.zip).toBe('');
  });

  it('persists changes via saveZip', () => {
    useCardpack.getState().load('admin');
    useCardpack.getState().saveZip('02134');
    expect(useCardpack.getState().pack.zip).toBe('02134');
    useCardpack.setState({ username: null, pack: { zip: '', cards: {} } });
    useCardpack.getState().load('admin');
    expect(useCardpack.getState().pack.zip).toBe('02134');
  });

  it('saveCard adds a new card', () => {
    useCardpack.getState().load('admin');
    useCardpack.getState().saveCard('wakefield', { barcode: '123', pin: '' });
    expect(useCardpack.getState().pack.cards.wakefield.barcode).toBe('123');
  });

  it('removeCard deletes', () => {
    useCardpack.getState().load('alex');
    useCardpack.getState().removeCard('wakefield');
    expect(useCardpack.getState().pack.cards.wakefield).toBeUndefined();
    expect(Object.keys(useCardpack.getState().pack.cards).length).toBe(4);
  });

  it('per-user namespace: alex and rbt do not share state', () => {
    useCardpack.getState().load('alex');
    useCardpack.getState().saveZip('02101');
    useCardpack.getState().load('rbt');
    expect(useCardpack.getState().pack.zip).toBe('01880');
    useCardpack.getState().load('alex');
    expect(useCardpack.getState().pack.zip).toBe('02101');
  });
});
