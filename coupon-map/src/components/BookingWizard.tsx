// BookingFloater — replaces the old 3-step BookingWizard with a single
// floating panel pinned to a specific (lib, attraction) pair. Cell-anchored
// (library is already chosen), so the panel only needs to:
//   1. show this pass's calendar with the same status colors the official
//      site uses (available / not-available / closed / not-yet-released);
//   2. show all stored cards with non-usable ones greyed out;
//   3. deep-link to the official booking page WITH the chosen date already
//      selected, so the user just pastes the card and confirms.
import { useEffect, useMemo, useState } from "react";
import type { Attraction, DataBundle, Library, Pass } from "../data/types";
import { matchCards } from "../lib/derive";
import { loadCards } from "../store/cards";

interface Props {
  bundle: DataBundle;
  attraction: Attraction;
  pass: Pass;
  lib: Library;
  onClose: () => void;
}

// Construct a deep URL that already lands on the chosen date on the
// official booking site. Pattern is platform-specific:
//   assabet → /museum-passes/by-date/YYYY-<month>/<day>/<slug>/
//   libcal  → ?date=YYYY-MM-DD appended
//   other   → fall back to the raw source_url (no deep-link possible)
function deepBookingUrl(pass: Pass, date: string | null): string {
  const url = pass.source_url || "";
  if (!url) return "";
  if (!date) return url;
  if (url.includes("assabetinteractive.com")) {
    const months = ["january", "february", "march", "april", "may", "june",
                    "july", "august", "september", "october", "november", "december"];
    const m = url.match(/\/museum-passes\/by-museum\/([^/]+)\//);
    if (m) {
      const slug = m[1];
      const [y, mo, d] = date.split("-");
      const monthName = months[parseInt(mo, 10) - 1];
      const base = url.split("/museum-passes/")[0];
      return `${base}/museum-passes/by-date/${y}-${monthName}/${parseInt(d, 10)}/${slug}/`;
    }
  }
  if (url.includes("libcal.com")) {
    return url + (url.includes("?") ? "&" : "?") + "date=" + date;
  }
  return url;
}

type DayStatus = "available" | "booked" | "closed" | "unavailable" | "none";

const STATUS_STYLE: Record<DayStatus, { bg: string; fg: string; label: string; click: boolean }> = {
  available:   { bg: "#C4DDCF", fg: "#1B5740", label: "Available",     click: true  },
  booked:      { bg: "#FDF1E2", fg: "#8C6018", label: "Not Available", click: false },
  closed:      { bg: "#ECEAE4", fg: "#4A4845", label: "Closed",        click: false },
  unavailable: { bg: "#F4F3EF", fg: "#B5B2A8", label: "Not Yet Released", click: false },
  none:        { bg: "#FAFAF7", fg: "#B5B2A8", label: "No Data",       click: false },
};

export default function BookingWizard({ bundle, attraction, pass, lib, onClose }: Props) {
  const avail = pass.availability || {};
  // Pick months: all months that appear in this pass's availability, sorted.
  const months = useMemo(() => {
    const s = new Set<string>();
    Object.keys(avail).forEach((d) => s.add(d.slice(0, 7)));
    return Array.from(s).sort();
  }, [avail]);
  const todayStr = new Date().toISOString().slice(0, 10);
  const initialMonth =
    months.find((m) => m >= todayStr.slice(0, 7)) || months[0] || todayStr.slice(0, 7);
  const [month, setMonth] = useState(initialMonth);
  const [date, setDate] = useState<string | null>(null);

  // My cards from localStorage. matchCards classifies them per pass.
  const cards = useMemo(() => loadCards(), []);
  const { exact, network } = useMemo(
    () => matchCards(cards, pass, bundle.libById),
    [cards, pass, bundle]
  );
  const exactIds = new Set(exact.map((c) => c.id));
  const networkIds = new Set(network.map((c) => c.id));
  const usableIds = new Set([...exactIds, ...networkIds]);

  const [selectedCardId, setSelectedCardId] = useState<string | null>(
    exact[0]?.id || network[0]?.id || null
  );
  const [copied, setCopied] = useState<string | null>(null);

  // Reset card selection if the auto-pick becomes invalid (rare here, but tidy).
  useEffect(() => {
    if (selectedCardId && !usableIds.has(selectedCardId)) setSelectedCardId(null);
  }, [selectedCardId, usableIds]);

  // ── Month grid ────────────────────────────────────────────────────────
  const [y, m] = month.split("-").map(Number);
  const monthFirst = new Date(Date.UTC(y, m - 1, 1));
  const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const leading = monthFirst.getUTCDay();
  const cells: Array<{ d: string | null; label: number | null }> = [];
  for (let i = 0; i < leading; i++) cells.push({ d: null, label: null });
  for (let i = 1; i <= daysInMonth; i++) {
    const ds = `${month}-${String(i).padStart(2, "0")}`;
    cells.push({ d: ds, label: i });
  }
  const mi = months.indexOf(month);

  const selectedCard = cards.find((c) => c.id === selectedCardId) || null;
  const jumpUrl = deepBookingUrl(pass, date);

  function copy(text: string) {
    navigator.clipboard.writeText(text).then(
      () => {
        setCopied(text);
        setTimeout(() => setCopied(null), 1500);
      },
      () => setCopied("复制失败")
    );
  }

  function onJump() {
    if (selectedCard) navigator.clipboard.writeText(selectedCard.card_number).catch(() => {});
    window.open(jumpUrl, "_blank", "noopener");
  }

  return (
    <div className="floater">
      <div className="floater-head">
        <div>
          <div className="floater-title">{attraction.name}</div>
          <div className="floater-sub">
            取件: <strong>{lib.town}</strong> ({lib.network}) · pass <code>{pass.coupon.summary}</code>
          </div>
        </div>
      </div>

      {/* Calendar */}
      <div className="floater-cal">
        <div className="cal-nav">
          <button onClick={() => mi > 0 && setMonth(months[mi - 1])} disabled={mi <= 0}>
            ← {months[mi - 1] || ""}
          </button>
          <strong>{month}</strong>
          <button
            onClick={() => mi < months.length - 1 && setMonth(months[mi + 1])}
            disabled={mi >= months.length - 1}
          >
            {months[mi + 1] || ""} →
          </button>
        </div>
        <div className="cal-week">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((w) => (
            <div key={w} className="cal-wh">{w}</div>
          ))}
        </div>
        <div className="cal-grid">
          {cells.map((c, i) => {
            if (!c.d) return <div key={i} className="cal-blank" />;
            const raw = avail[c.d];
            const status: DayStatus =
              raw === "available" ? "available" :
              raw === "booked" ? "booked" :
              raw === "closed" ? "closed" :
              raw === "unavailable" ? "unavailable" : "none";
            const st = STATUS_STYLE[status];
            const past = c.d < todayStr;
            const isSelected = c.d === date;
            const disabled = past || !st.click;
            return (
              <button
                key={c.d}
                className={`cal-cell${isSelected ? " selected" : ""}`}
                disabled={disabled}
                style={{ background: st.bg, color: st.fg, opacity: past ? 0.35 : 1 }}
                onClick={() => setDate(c.d!)}
                title={`${c.d} — ${st.label}`}
              >
                <span className="cal-day">{c.label}</span>
                <span className="cal-tag">{st.label}</span>
              </button>
            );
          })}
        </div>
        <div className="cal-legend">
          {(["available","booked","closed","unavailable"] as DayStatus[]).map((s) => (
            <span key={s} className="lg">
              <span className="lg-sw" style={{ background: STATUS_STYLE[s].bg }} />
              {STATUS_STYLE[s].label}
            </span>
          ))}
        </div>
      </div>

      {/* My cards */}
      <div className="floater-cards">
        <div className="cards-h">我的卡 · 可用 {usableIds.size} / {cards.length}</div>
        {cards.length === 0 && (
          <div className="cards-empty">还没有卡。去「我的卡」tab 添加或导入。</div>
        )}
        {cards.map((c) => {
          const usable = usableIds.has(c.id);
          const role = exactIds.has(c.id) ? "本馆卡" : networkIds.has(c.id) ? "同 network 卡" : "不适用";
          const cardLib = bundle.libById.get(c.library_id);
          const selected = c.id === selectedCardId;
          return (
            <div
              key={c.id}
              className={`card-pick${usable ? "" : " disabled"}${selected ? " selected" : ""}`}
              onClick={() => usable && setSelectedCardId(c.id)}
            >
              <div className="cp-main">
                <div className="cp-name">
                  {cardLib ? `${cardLib.town} (${cardLib.network})` : c.library_id}
                  <span className="cp-role">{usable ? `✓ ${role}` : `· ${role}`}</span>
                </div>
                <div className="cp-meta">
                  <code className="cp-barcode">{c.card_number}</code>
                  <button
                    className="cp-copy"
                    onClick={(e) => { e.stopPropagation(); copy(c.card_number); }}
                    title="复制卡号"
                  >
                    复制
                  </button>
                  {c.note && <span className="cp-note">{c.note}</span>}
                </div>
              </div>
              {usable && (
                <input
                  type="radio"
                  className="cp-radio"
                  checked={selected}
                  onChange={() => setSelectedCardId(c.id)}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Jump */}
      <div className="floater-foot">
        <div className="foot-status">
          {date ? <>选定: <strong>{date}</strong></> : <>未选日期</>}
          {selectedCard && (
            <> · 卡号 <code>{selectedCard.card_number}</code></>
          )}
        </div>
        <div className="foot-btns">
          <button onClick={onClose} className="btn-ghost">关闭</button>
          <button
            onClick={onJump}
            disabled={!date}
            className="btn-primary"
            title={!date ? "先选日期" : "复制卡号 + 在新标签打开预定页"}
          >
            去预定 ↗ {selectedCard && "(已复制卡号)"}
          </button>
        </div>
        {copied && <div className="copy-toast">已复制: {copied.length > 16 ? copied.slice(0, 16) + "…" : copied}</div>}
      </div>
    </div>
  );
}
