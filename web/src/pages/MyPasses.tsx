import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import { Input, Button } from '@heroui/react';
import { useAuth } from '../auth/store';
import { useCardpack, type LibraryCard } from '../stores/cardpack';
import { getLibraries } from '../data/load';

export function MyPasses() {
  const user = useAuth(s => s.currentUser);
  const pack = useCardpack(s => s.pack);
  const load = useCardpack(s => s.load);
  const saveCard = useCardpack(s => s.saveCard);
  const removeCard = useCardpack(s => s.removeCard);

  useEffect(() => { load(user?.username ?? null); }, [user, load]);

  // Sort libraries alphabetically by full library name (A → Z). Town was the
  // old sort key but the user reads names, not towns.
  const libraries = useMemo(() => {
    const list = getLibraries();
    return [...list].sort((a, b) => a.name.localeCompare(b.name));
  }, []);

  const [search, setSearch] = useState('');

  const visibleLibraries = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return libraries;
    return libraries.filter(
      l => l.name.toLowerCase().includes(q) || l.town.toLowerCase().includes(q),
    );
  }, [libraries, search]);

  if (!user) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-6">
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
        <p style={{ marginTop: 12, color: 'var(--ink-3)' }}>Sign in to manage your cards.</p>
      </div>
    );
  }

  const heldCount = Object.values(pack.cards).filter(c => !!c?.barcode).length;

  return (
    <div className="max-w-3xl mx-auto" style={{ minHeight: '100vh', background: 'var(--white)' }}>
      {/* Sticky header: back chevron + title on top row, search input below. */}
      <header
        className="sticky"
        style={{
          top: 0, zIndex: 30, background: 'var(--white)',
          borderBottom: '1px solid var(--rule)',
          padding: '10px 14px',
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          <Link
            to="/"
            aria-label="Back to attractions"
            className="inline-flex items-center justify-center"
            style={{
              width: 32, height: 32, borderRadius: 8,
              color: 'var(--ink-2)', textDecoration: 'none',
              flexShrink: 0,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </Link>
          <h1 style={{
            fontSize: 18, fontWeight: 700, color: 'var(--ink-2)',
            margin: 0, flexGrow: 1, minWidth: 0,
          }}>
            My library cards
            {heldCount > 0 && (
              <span style={{
                marginLeft: 8, fontSize: 13, fontWeight: 500, color: 'var(--g)',
              }}>{heldCount}</span>
            )}
          </h1>
        </div>
        <Input
          size="sm"
          value={search}
          onValueChange={setSearch}
          placeholder="Search by library or town"
          aria-label="Search libraries"
          startContent={
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round" aria-hidden
              style={{ color: 'var(--ink-3)' }}>
              <circle cx="11" cy="11" r="7"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          }
        />
      </header>

      {/* Library list */}
      <div style={{ padding: '4px 14px 32px' }}>
        {visibleLibraries.length === 0 && (
          <p style={{ marginTop: 16, color: 'var(--ink-3)', fontSize: 13, textAlign: 'center' }}>
            No libraries match "{search}".
          </p>
        )}
        {visibleLibraries.map(l => {
          const card = pack.cards[l.id];
          const has = !!card;
          return (
            <LibraryRow
              key={l.id}
              libraryId={l.id}
              libraryName={l.name}
              town={l.town}
              card={card}
              hasCard={has}
              onAdd={() => saveCard(l.id, { barcode: '' })}
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
  libraryId: string;
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
  const [draft, setDraft] = useState<LibraryCard>(card ?? { barcode: '' });

  useEffect(() => {
    if (card) setDraft(card);
  }, [card]);

  const handleAddOrToggle = () => {
    if (!hasCard) onAdd();
    setOpen(o => !o);
  };

  const filled = !!card?.barcode;

  return (
    <div style={{ borderBottom: '1px solid var(--rule)' }}>
      {/* Row header — single tap target. Left indicator pill shows status,
          right caret reveals/hides the edit form. */}
      <button
        type="button"
        onClick={handleAddOrToggle}
        className="flex items-center gap-3 w-full text-left"
        style={{
          background: 'transparent', border: 'none', padding: '12px 4px',
          cursor: 'pointer', font: 'inherit',
        }}
      >
        {/* Status pill: green check whenever the user has marked this card as
            held — regardless of whether they've entered the barcode yet.
            Some users just want to flag the cards they own without typing
            digits, and the check confirms the selection registered. */}
        <span
          aria-hidden
          style={{
            width: 18, height: 18, borderRadius: '50%',
            background: hasCard ? 'var(--g)' : 'transparent',
            border: `1.5px solid ${hasCard ? 'var(--g)' : 'var(--rule-strong)'}`,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
            color: hasCard ? 'var(--white)' : 'var(--ink-3)',
          }}
        >
          {hasCard && (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={3}
              strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          )}
        </span>
        <span style={{ flexGrow: 1, minWidth: 0 }}>
          <span style={{
            fontWeight: 500, color: 'var(--ink-2)', fontSize: 14,
            display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{libraryName}</span>
          <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>{town}</span>
        </span>
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth={2}
          strokeLinecap="round" strokeLinejoin="round" aria-hidden
          style={{
            color: 'var(--ink-3)', flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 0.15s',
          }}
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      {hasCard && open && (
        <div style={{ padding: '4px 4px 14px 30px' }}>
          {/* Card number + Save on one row. PIN was dropped — only the
              barcode is ever pasted into the library's pickup form, and
              we don't need to collect the user's PIN. */}
          <div className="flex items-center gap-2">
            <Input
              size="sm"
              value={draft.barcode}
              onValueChange={(v) => setDraft({ ...draft, barcode: v })}
              placeholder="Card number"
              aria-label="Card number (optional)"
              className="flex-grow"
              endContent={
                <span style={{
                  fontSize: 11, color: 'var(--ink-3)',
                  fontStyle: 'italic', whiteSpace: 'nowrap',
                }}>optional</span>
              }
            />
            <Button
              size="sm"
              color="primary"
              onClick={() => { onSave(draft); setOpen(false); }}
              style={{ background: 'var(--g)', color: 'var(--white)' }}
              className="flex-shrink-0"
            >
              Save
            </Button>
          </div>
          <button
            type="button"
            onClick={() => { onRemove(); setOpen(false); }}
            style={{
              marginTop: 8, background: 'transparent', border: 'none',
              color: 'var(--rd)', fontSize: 12, padding: 0, cursor: 'pointer',
            }}
          >
            Remove this card
          </button>
        </div>
      )}
    </div>
  );
}
