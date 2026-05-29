// LocalStorage-backed card store. Cards (with barcodes) NEVER leave the browser
// unless the user explicitly exports JSON. Import/export lets the same user
// rehydrate on a new machine without going through git.
import type { StoredCard } from "../lib/derive";

const KEY = "coupon-map.cards.v1";

export function loadCards(): StoredCard[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((c) => c && typeof c.library_id === "string" && typeof c.card_number === "string");
  } catch {
    return [];
  }
}

export function saveCards(cards: StoredCard[]) {
  localStorage.setItem(KEY, JSON.stringify(cards));
}

export function newId() {
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function exportCards(cards: StoredCard[]) {
  const blob = new Blob([JSON.stringify(cards, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `coupon-map-cards-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function importCardsFromFile(file: File): Promise<StoredCard[]> {
  const text = await file.text();
  const parsed = JSON.parse(text);
  if (!Array.isArray(parsed)) throw new Error("导入文件根必须是数组");
  return parsed.map((c: Partial<StoredCard>, i) => {
    if (!c.library_id || !c.card_number) throw new Error(`第 ${i + 1} 条缺 library_id 或 card_number`);
    return {
      id: c.id ?? newId(),
      library_id: String(c.library_id),
      card_number: String(c.card_number),
      note: c.note ? String(c.note) : "",
      enabled: c.enabled === false ? false : true,
    };
  });
}
