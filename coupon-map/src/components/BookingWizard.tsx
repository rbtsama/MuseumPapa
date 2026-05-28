// BookingFloater — opens from the Pass cell. Two columns:
//   Date (left)  ·  Card (right).
// User picks a date from the calendar; user picks a card from their wallet
// (non-usable cards rendered greyed-out, non-clickable, no "Not Eligible"
// label). When both are selected, the Book button lights up and clicking
// it copies the selected card's number to the clipboard and opens the
// official booking page deep-linked to that date.
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
// official booking site. Platform-specific:
//   assabet → /by-date/YYYY-<month>/<day>/<slug>/
//   libcal  → ?date=YYYY-MM-DD appended
//   other   → raw source_url
function deepBookingUrl(pass: Pass, date: string | null): string {
  const url = pass.source_url || "";
  if (!url) return "";
  if (!date) return url;
  if (url.includes("assabetinteractive.com")) {
    const months = ["january","february","march","april","may","june",
                    "july","august","september","october","november","december"];
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
  unavailable: { bg: "#F4F3EF", fg: "#B5B2A8", label: "Not Released",  click: false },
  none:        { bg: "#FAFAF7", fg: "#B5B2A8", label: "No Data",       click: false },
};

export default function BookingWizard({ bundle, attraction, pass, lib, onClose }: Props) {
  const avail = pass.availability || {};
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

  const cards = useMemo(() => loadCards(), []);
  const { exact, network } = useMemo(
    () => matchCards(cards, pass, bundle.libById),
    [cards, pass, bundle]
  );
  const exactIds = new Set(exact.map((c) => c.id));
  const networkIds = new Set(network.map((c) => c.id));
  const usableIds = new Set([...exactIds, ...networkIds]);

  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const selectedCard = cards.find((c) => c.id === selectedCardId) || null;

  // If a card we had pre-selected stops being usable, drop it.
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

  function onBook() {
    if (!date || !selectedCard) return;
    navigator.clipboard.writeText(selectedCard.card_number).catch(() => {});
    window.open(deepBookingUrl(pass, date), "_blank", "noopener");
  }

  const ready = Boolean(date && selectedCard);

  return (
    <div className="floater">
      <div className="floater-head">
        <div className="floater-title">{attraction.name}</div>
        <div className="floater-sub">
          Pickup at <strong>{lib.town}</strong> ({lib.network}) · <code>{pass.coupon.summary}</code>
        </div>
      </div>

      <div className="floater-body">
        {/* Date column */}
        <div className="floater-cal">
          <div className="col-hint">
            {date ? <>Date: <strong>{date}</strong></> : <>Please select a date</>}
          </div>
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

        {/* Card column */}
        <div className="floater-cards">
          <div className="col-hint">
            {selectedCard ? (
              <>Card: <strong>{bundle.libById.get(selectedCard.library_id)?.town || selectedCard.library_id}</strong></>
            ) : (
              <>Please select a card to book</>
            )}
          </div>
          {cards.length === 0 && (
            <div className="cards-empty">No cards yet. Add or import from "My Cards".</div>
          )}
          {cards.map((c) => {
            const usable = usableIds.has(c.id);
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
                    {cardLib ? cardLib.town : c.library_id}
                    {cardLib && <span className="cp-net">{cardLib.network}</span>}
                  </div>
                  <div className="cp-meta">
                    <code className="cp-barcode">{c.card_number}</code>
                    {c.note && <span className="cp-note">{c.note}</span>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer — Book button enabled only when both date and card chosen. */}
      <div className="floater-foot">
        <div className="foot-btns">
          <button onClick={onClose} className="btn-ghost">Close</button>
          <button
            onClick={onBook}
            disabled={!ready}
            className="btn-primary"
            title={!date ? "Pick a date first" : !selectedCard ? "Pick a card" : "Copy card & open booking page"}
          >
            Book ↗
          </button>
        </div>
      </div>
    </div>
  );
}
