import { useEffect, useRef, useState } from "react";
import type { DataBundle } from "../data/types";
import { exportCards, importCardsFromFile, loadCards, newId, saveCards } from "../store/cards";
import type { StoredCard } from "../lib/derive";

interface Props { bundle: DataBundle }

export default function MyCards({ bundle }: Props) {
  const [cards, setCards] = useState<StoredCard[]>([]);
  const [draft, setDraft] = useState<StoredCard>({ id: "", library_id: "", card_number: "", note: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const [copyHint, setCopyHint] = useState<string | null>(null);

  useEffect(() => { setCards(loadCards()); }, []);

  function persist(next: StoredCard[]) { setCards(next); saveCards(next); }
  function add() {
    if (!draft.library_id || !draft.card_number.trim()) return;
    const c: StoredCard = { ...draft, id: newId(), card_number: draft.card_number.trim(), note: draft.note?.trim() };
    persist([...cards, c]);
    setDraft({ id: "", library_id: "", card_number: "", note: "" });
  }
  function remove(id: string) { persist(cards.filter((c) => c.id !== id)); }
  function copy(text: string) {
    navigator.clipboard.writeText(text).then(
      () => { setCopyHint("Copied"); setTimeout(() => setCopyHint(null), 1200); },
      () => setCopyHint("Copy failed")
    );
  }
  async function onImport(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const imported = await importCardsFromFile(f);
      if (confirm(`Import ${imported.length} card(s)? This will replace the current ${cards.length}.`)) {
        persist(imported);
      }
    } catch (err) {
      alert("Import failed: " + (err as Error).message);
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div className="my-cards">
      <div className="my-cards-head">
        <div>
          <h2>My Library Cards</h2>
          <div className="meta">{cards.length} stored · localStorage only, never committed</div>
        </div>
        <div className="my-cards-actions">
          <button onClick={() => fileRef.current?.click()} className="mc-btn">Import JSON</button>
          <button onClick={() => exportCards(cards)} className="mc-btn" disabled={cards.length === 0}>Export JSON</button>
          <input ref={fileRef} type="file" accept="application/json" hidden onChange={onImport} />
        </div>
      </div>

      <div className="add-form">
        <div className="field">
          <label className="field-label">Library</label>
          <select
            value={draft.library_id}
            onChange={(e) => setDraft({ ...draft, library_id: e.target.value })}
          >
            <option value="">— Select town —</option>
            {bundle.networks.map((g) => (
              <optgroup key={g.network} label={g.network}>
                {g.libraries.map((l) => (
                  <option key={l.id} value={l.id}>{l.town}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field-label">Card number</label>
          <input
            className="mono"
            value={draft.card_number}
            onChange={(e) => setDraft({ ...draft, card_number: e.target.value })}
          />
        </div>
        <div className="field">
          <label className="field-label">Note</label>
          <input
            placeholder="e.g. primary"
            value={draft.note || ""}
            onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          />
        </div>
        <button onClick={add} className="mc-btn primary" disabled={!draft.library_id || !draft.card_number.trim()}>
          + Add
        </button>
      </div>

      {cards.length === 0 ? (
        <div className="mc-empty">No cards yet. Duplicates per library are allowed.</div>
      ) : (
        <div className="cards-table">
          <div className="ct-head">
            <span>Library</span>
            <span>Card number</span>
            <span>Note</span>
            <span></span>
          </div>
          {cards.map((c) => {
            const lib = bundle.libById.get(c.library_id);
            return (
              <div key={c.id} className="ct-row">
                <span className="ct-lib">
                  {lib ? (
                    <>
                      <strong>{lib.town}</strong>
                      <span className="ct-net">{lib.network}</span>
                    </>
                  ) : (
                    <span className="ct-warn">⚠ {c.library_id}</span>
                  )}
                </span>
                <span className="ct-card">
                  <code>{c.card_number}</code>
                  <button onClick={() => copy(c.card_number)} className="mc-btn tiny" title="Copy">Copy</button>
                </span>
                <span className="ct-note">{c.note || "—"}</span>
                <button onClick={() => remove(c.id)} className="mc-btn tiny ghost" title="Delete">×</button>
              </div>
            );
          })}
        </div>
      )}

      {copyHint && <div className="copy-toast-fixed">{copyHint}</div>}
    </div>
  );
}
