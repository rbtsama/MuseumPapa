import { useEffect, useMemo, useRef, useState } from "react";
import type { DataBundle } from "../data/types";
import { exportCards, importCardsFromFile, loadCards, newId, saveCards } from "../store/cards";
import type { StoredCard } from "../lib/derive";

interface Props { bundle: DataBundle }

export default function MyCards({ bundle }: Props) {
  const [cards, setCards] = useState<StoredCard[]>([]);
  const [draft, setDraft] = useState<StoredCard>({ id: "", library_id: "", card_number: "", note: "" });
  const fileRef = useRef<HTMLInputElement>(null);
  const [copyHint, setCopyHint] = useState<string | null>(null);

  useEffect(() => {
    setCards(loadCards());
  }, []);

  // Library options: 59 entries, town as label, sorted by network then town.
  const options = useMemo(() => {
    const out: Array<{ id: string; label: string; network: string }> = [];
    for (const g of bundle.networks) {
      for (const l of g.libraries) out.push({ id: l.id, label: `${l.town} (${g.network})`, network: g.network });
    }
    return out;
  }, [bundle]);

  function persist(next: StoredCard[]) {
    setCards(next);
    saveCards(next);
  }

  function add() {
    if (!draft.library_id || !draft.card_number.trim()) return;
    const c: StoredCard = { ...draft, id: newId(), card_number: draft.card_number.trim(), note: draft.note?.trim() };
    persist([...cards, c]);
    setDraft({ id: "", library_id: "", card_number: "", note: "" });
  }

  function remove(id: string) {
    persist(cards.filter((c) => c.id !== id));
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text).then(
      () => {
        setCopyHint("已复制");
        setTimeout(() => setCopyHint(null), 1200);
      },
      () => setCopyHint("复制失败")
    );
  }

  async function onImport(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const imported = await importCardsFromFile(f);
      if (confirm(`导入 ${imported.length} 条卡数据,将覆盖现有 ${cards.length} 条,确认?`)) {
        persist(imported);
      }
    } catch (err) {
      alert("导入失败: " + (err as Error).message);
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div>
      <div className="filter-bar">
        <strong style={{ marginRight: 8 }}>我的图书馆卡</strong>
        <span style={{ color: "#4a4845" }}>{cards.length} 条 · 仅存本机浏览器(localStorage),严禁进 git</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => exportCards(cards)} style={btnGhost}>
            导出 JSON
          </button>
          <button onClick={() => fileRef.current?.click()} style={btnGhost}>
            导入 JSON
          </button>
          <input ref={fileRef} type="file" accept="application/json" hidden onChange={onImport} />
        </span>
      </div>

      {/* add form */}
      <div className="card-row" style={{ borderBottom: "1px solid #d0cec6", paddingBottom: 8 }}>
        <select
          value={draft.library_id}
          onChange={(e) => setDraft({ ...draft, library_id: e.target.value })}
        >
          <option value="">-- 选择图书馆 (town) --</option>
          {bundle.networks.map((g) => (
            <optgroup key={g.network} label={g.network}>
              {g.libraries.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.town}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <input
          className="barcode"
          placeholder="卡号 / barcode"
          value={draft.card_number}
          onChange={(e) => setDraft({ ...draft, card_number: e.target.value })}
        />
        <input
          placeholder="备注 (例: 旧卡 / 主用)"
          value={draft.note || ""}
          onChange={(e) => setDraft({ ...draft, note: e.target.value })}
        />
        <button onClick={add} style={btnPrimary} disabled={!draft.library_id || !draft.card_number.trim()}>
          添加
        </button>
      </div>

      {cards.length === 0 && (
        <div style={{ padding: "16px 0", color: "#4a4845", fontStyle: "italic" }}>
          还没有卡。同一馆可添加多条(允许重复)。
        </div>
      )}

      {/* list */}
      {cards.map((c) => {
        const lib = bundle.libById.get(c.library_id);
        const town = lib ? `${lib.town} (${lib.network})` : `⚠ 未知馆: ${c.library_id}`;
        return (
          <div key={c.id} className="card-row">
            <span>{town}</span>
            <span className="barcode" style={{ fontWeight: 600 }}>
              {c.card_number}{" "}
              <button onClick={() => copy(c.card_number)} style={btnTiny} title="复制卡号">
                复制
              </button>
            </span>
            <span style={{ color: "#4a4845" }}>{c.note || "—"}</span>
            <button onClick={() => remove(c.id)} style={btnGhost}>
              删除
            </button>
          </div>
        );
      })}

      {copyHint && (
        <div
          style={{
            position: "fixed",
            bottom: 20,
            right: 20,
            background: "#1B5740",
            color: "#FAFAF7",
            padding: "6px 14px",
            borderRadius: 4,
            fontSize: 12,
          }}
        >
          {copyHint}
        </div>
      )}
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  padding: "5px 12px",
  background: "#1B5740",
  color: "#FAFAF7",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 600,
};
const btnGhost: React.CSSProperties = {
  padding: "4px 10px",
  background: "#FAFAF7",
  color: "#1a1917",
  border: "1px solid #D0CEC6",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 12,
};
const btnTiny: React.CSSProperties = {
  padding: "1px 6px",
  background: "#EAF1EE",
  color: "#1B5740",
  border: "1px solid #C4DDCF",
  borderRadius: 3,
  cursor: "pointer",
  fontSize: 10,
  marginLeft: 4,
};
