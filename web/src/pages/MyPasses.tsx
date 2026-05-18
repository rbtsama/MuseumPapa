import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Input, Button, Checkbox } from '@heroui/react';
import { useAuth } from '../auth/store';
import { useCardpack, type LibraryCard } from '../stores/cardpack';
import { getLibraries } from '../data/load';

export function MyPasses() {
  const user = useAuth(s => s.currentUser);
  const pack = useCardpack(s => s.pack);
  const load = useCardpack(s => s.load);
  const saveZip = useCardpack(s => s.saveZip);
  const saveCard = useCardpack(s => s.saveCard);
  const removeCard = useCardpack(s => s.removeCard);

  useEffect(() => { load(user?.username ?? null); }, [user, load]);

  const libraries = useMemo(() => {
    const list = getLibraries();
    return [...list].sort((a, b) => a.town.localeCompare(b.town));
  }, []);

  const [zipDraft, setZipDraft] = useState('');
  useEffect(() => { setZipDraft(pack.zip); }, [pack.zip]);

  const [search, setSearch] = useState('');
  const [onlyMine, setOnlyMine] = useState(false);

  const visibleLibraries = useMemo(() => {
    const q = search.trim().toLowerCase();
    return libraries.filter(l => {
      if (onlyMine && !pack.cards[l.id]) return false;
      if (!q) return true;
      return l.name.toLowerCase().includes(q) || l.town.toLowerCase().includes(q);
    });
  }, [libraries, search, onlyMine, pack.cards]);

  if (!user) {
    return <div className="max-w-3xl mx-auto px-4 py-6">
      <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
      <p style={{ marginTop: 12, color: 'var(--ink-3)' }}>Sign in to manage your passes.</p>
    </div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div style={{ marginBottom: 12 }}>
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
      </div>
      <h1 style={{ fontSize: 22, marginBottom: 4, color: 'var(--ink-2)', fontWeight: 700 }}>
        My passes
      </h1>
      <p style={{ color: 'var(--ink-3)', fontSize: 12, marginBottom: 16 }}>
        Stored only in your browser, tied to your account.
      </p>

      <div style={{ borderBottom: '1px solid var(--rule)', paddingBottom: 16, marginBottom: 16 }}>
        <h2 style={{ fontSize: 13, fontWeight: 500, marginBottom: 8, color: 'var(--ink-2)' }}>ZIP code</h2>
        <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}>
          <Input
            size="sm"
            value={zipDraft}
            onValueChange={setZipDraft}
            placeholder="01880"
            maxLength={5}
            className="max-w-[160px]"
          />
          <Button size="sm" color="primary" onClick={() => saveZip(zipDraft)}>
            Save
          </Button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4 }}>
          Used to calculate distance to pickup libraries.
        </p>
      </div>

      <h2 style={{ fontSize: 13, fontWeight: 500, marginBottom: 8, color: 'var(--ink-2)' }}>
        Your library cards ({Object.keys(pack.cards).length})
      </h2>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
        <Input
          size="sm"
          value={search}
          onValueChange={setSearch}
          placeholder="Search libraries by name or town…"
          className="max-w-[320px]"
          aria-label="Search libraries"
        />
        <Checkbox
          size="sm"
          isSelected={onlyMine}
          onValueChange={setOnlyMine}
        >
          Only my cards
        </Checkbox>
        <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
          {visibleLibraries.length} of {libraries.length} shown
        </span>
      </div>

      <p style={{ fontSize: 11, color: 'var(--ink-3)', marginBottom: 12, fontStyle: 'italic' }}>
        Without these we can't autofill the library's pickup page for you, but you can still browse coupons.
      </p>

      <div>
        {visibleLibraries.map(l => {
          const card = pack.cards[l.id];
          const has = !!card;
          return (
            <LibraryRow
              key={l.id}
              libraryName={l.name}
              town={l.town}
              card={card}
              hasCard={has}
              onAdd={() => saveCard(l.id, { barcode: '', pin: '' })}
              onSave={(updates) => saveCard(l.id, updates)}
              onRemove={() => removeCard(l.id)}
            />
          );
        })}
      </div>
    </div>
  );
}

interface RowProps {
  libraryName: string;
  town: string;
  card?: LibraryCard;
  hasCard: boolean;
  onAdd: () => void;
  onSave: (updates: LibraryCard) => void;
  onRemove: () => void;
}

function LibraryRow({ libraryName, town, card, hasCard, onAdd, onSave, onRemove }: RowProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<LibraryCard>(card ?? { barcode: '', pin: '' });

  useEffect(() => {
    if (card) setDraft(card);
  }, [card]);

  return (
    <div style={{ borderBottom: '1px solid var(--rule)', padding: '10px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Checkbox
          size="sm"
          isSelected={hasCard}
          onValueChange={(checked) => {
            if (checked) { onAdd(); setOpen(true); }
            else onRemove();
          }}
        />
        <button
          onClick={() => setOpen(o => !o)}
          style={{
            flex: 1, textAlign: 'left', background: 'transparent', border: 'none',
            cursor: 'pointer', font: 'inherit', padding: 0,
          }}
        >
          <span style={{ fontWeight: 500, color: 'var(--ink-2)', fontSize: 13 }}>{libraryName}</span>
          <span style={{ color: 'var(--ink-3)', marginLeft: 8, fontSize: 13 }}>· {town}</span>
        </button>
      </div>
      {hasCard && open && (
        <div style={{ marginLeft: 32, marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Input
            label="Barcode (optional)"
            size="sm"
            value={draft.barcode}
            onValueChange={(v) => setDraft({ ...draft, barcode: v })}
            className="max-w-[220px]"
          />
          <Input
            label="PIN (optional)"
            size="sm"
            value={draft.pin}
            onValueChange={(v) => setDraft({ ...draft, pin: v })}
            className="max-w-[120px]"
          />
          <Button size="sm" color="primary" onClick={() => { onSave(draft); setOpen(false); }}>
            Save
          </Button>
        </div>
      )}
    </div>
  );
}
