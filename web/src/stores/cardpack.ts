import { create } from 'zustand';
import { lsGetUser, lsSetUser } from '../lib/localStorage';

export interface LibraryCard {
  // The library-card barcode the user enters at /settings/passes. Only field
  // we collect — PIN was deliberately removed (we don't ask for PII beyond
  // what's needed, and the library's pickup page can only autofill one
  // thing from clipboard anyway).
  barcode: string;
}

export interface CardPack {
  zip: string;
  cards: Record<string, LibraryCard>;
}

const EMPTY: CardPack = { zip: '', cards: {} };

const SEEDS: Record<string, CardPack> = {
  alex: {
    zip: '01880',
    cards: {
      wakefield: { barcode: '21000000000001'},
      reading:   { barcode: '21000000000002'},
      bpl:       { barcode: '21000000000003'},
      wilmington:{ barcode: '21000000000004'},
      somerville:{ barcode: '21000000000005'},
    },
  },
  rbt: {
    zip: '01880',
    cards: {
      wakefield: { barcode: '21000000009999'},
    },
  },
  admin: { zip: '', cards: {} },
};

interface CardpackState {
  username: string | null;
  pack: CardPack;
  load: (username: string | null) => void;
  saveZip: (zip: string) => void;
  saveCard: (libId: string, card: LibraryCard) => void;
  removeCard: (libId: string) => void;
}

export const useCardpack = create<CardpackState>((set, get) => ({
  username: null,
  pack: EMPTY,

  load: (username) => {
    const stored = lsGetUser<CardPack | null>(username, 'cardpack', null);
    let pack: CardPack;
    if (stored) {
      pack = stored;
    } else if (username && SEEDS[username]) {
      pack = SEEDS[username];
      lsSetUser(username, 'cardpack', pack);
    } else {
      pack = EMPTY;
    }
    set({ username, pack });
  },

  saveZip: (zip) => {
    const { username, pack } = get();
    const next = { ...pack, zip };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },

  saveCard: (libId, card) => {
    const { username, pack } = get();
    const next = { ...pack, cards: { ...pack.cards, [libId]: card } };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },

  removeCard: (libId) => {
    const { username, pack } = get();
    const cards = { ...pack.cards };
    delete cards[libId];
    const next = { ...pack, cards };
    lsSetUser(username, 'cardpack', next);
    set({ pack: next });
  },
}));
