// BookingDrawer — right-side slide-in panel (380px) opened by clicking a
// pass cell. Replaces the previous popover-on-cell + modal-on-Book chain.
// One vertical panel holds: pass facts, audit (Approve / Edit), booking
// (date + card + Book). Backdrop click / Esc closes. Book copies the card
// number to clipboard, opens the deep-linked booking page in a new tab,
// and closes the drawer.
import { useEffect, useMemo, useState } from "react";
import type { Attraction, Branch, DataBundle, Library, Pass } from "../data/types";
import {
  audienceLabel,
  capacityStructure,
  formLabel,
  frequencyLimit,
  matchCards,
  passResidencyLabel,
  policyRange,
  policyText,
  verdictLabel,
} from "../lib/derive";
import { loadCards } from "../store/cards";
import { AUDITABLE_FIELDS } from "../store/audit";

export interface DrawerCtx {
  attr: Attraction;
  lib: Library;
  branch: Branch | null;
  pass: Pass;
}

interface AuditEntry {
  approved?: { at: string };
  corrections?: { at: string; notes: Record<string, string> };
}

interface Props {
  bundle: DataBundle;
  ctx: DrawerCtx | null;        // null = closed
  entry?: AuditEntry;
  onClose: () => void;
  onToggleApprove: () => void;
  onSetCorrection: (field: string, note: string) => void;
}

// ── Booking deep-link (same logic as the old BookingWizard) ─────────────
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

function prettyHost(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "") + (u.pathname && u.pathname !== "/" ? u.pathname : "");
  } catch {
    return url;
  }
}

export default function BookingDrawer({ bundle, ctx, entry, onClose, onToggleApprove, onSetCorrection }: Props) {
  // ── Esc to close ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!ctx) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ctx, onClose]);

  // Reset internal selection state every time ctx changes
  const [date, setDate] = useState<string | null>(null);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [showEdit, setShowEdit] = useState(false);
  useEffect(() => {
    setDate(null);
    setSelectedCardId(null);
    setShowEdit(false);
  }, [ctx?.attr.slug, ctx?.lib.id, ctx?.branch?.id]);

  // Always render the shell so the close transition can play; gate by `open`.
  const open = !!ctx;

  // ── month grid ────────────────────────────────────────────────────────
  // Assabet passes: fetch fresh availability on demand from /api/availability
  // (live calendar overlay; cached 15 min at the edge). Other platforms
  // stay on the build-time snapshot and surface a "non-realtime" banner.
  const sourceUrl = ctx?.pass.source_url || "";
  const isAssabet = sourceUrl.includes("assabetinteractive.com");
  const [liveAvail, setLiveAvail] = useState<Record<string, string> | null>(null);
  const [liveStatus, setLiveStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");

  // Static snapshot from passes.json (the merge target / fallback).
  const staticAvail = ctx?.pass.availability || {};
  const avail = liveAvail ? { ...staticAvail, ...liveAvail } : staticAvail;

  const months = useMemo(() => {
    const s = new Set<string>();
    // Show months from BOTH the static snapshot AND today's calendar window
    // so the user always sees at least the current + next month even if the
    // static snapshot is stale.
    Object.keys(staticAvail).forEach((d) => s.add(d.slice(0, 7)));
    const today = new Date();
    for (let i = 0; i < 3; i++) {
      const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
      s.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
    }
    return Array.from(s).sort();
  }, [staticAvail]);
  const todayStr = new Date().toISOString().slice(0, 10);
  const initialMonth = months.find((m) => m >= todayStr.slice(0, 7)) || months[0] || todayStr.slice(0, 7);
  const [month, setMonth] = useState(initialMonth);
  useEffect(() => { setMonth(initialMonth); }, [initialMonth]);

  // Live-fetch Assabet availability for the visible month. Re-runs when the
  // user navigates to a different month or opens a different pass. Other
  // platforms skip the fetch entirely.
  useEffect(() => {
    if (!ctx || !isAssabet || !sourceUrl) {
      setLiveAvail(null);
      setLiveStatus("idle");
      return;
    }
    let cancelled = false;
    setLiveStatus("loading");
    const qs = new URLSearchParams({ url: sourceUrl, month });
    fetch(`/api/availability?${qs}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((data: { days: Record<string, string> }) => {
        if (cancelled) return;
        setLiveAvail((prev) => ({ ...(prev || {}), ...(data.days || {}) }));
        setLiveStatus("ok");
      })
      .catch(() => { if (!cancelled) setLiveStatus("error"); });
    return () => { cancelled = true; };
  }, [ctx?.pass.source_url, isAssabet, sourceUrl, month]);

  // ── card matching ─────────────────────────────────────────────────────
  const cards = useMemo(() => loadCards(), [ctx?.attr.slug, ctx?.lib.id]);
  const { exact, network } = useMemo(
    () => (ctx ? matchCards(cards, ctx.pass, bundle.libById) : { exact: [], network: [] }),
    [cards, ctx, bundle]
  );
  const usableIds = useMemo(() => new Set([...exact, ...network].map((c) => c.id)), [exact, network]);
  const selectedCard = cards.find((c) => c.id === selectedCardId) || null;
  // (Previously: auto-deselect when a card stopped being usable. Removed —
  // greyed cards are now soft warnings, not locks; deselecting under the
  // user's feet would silently undo their explicit "I'll try it anyway"
  // choice.)

  function onBook() {
    if (!ctx || !date || !selectedCard) return;
    navigator.clipboard.writeText(selectedCard.card_number).catch(() => {});
    window.open(deepBookingUrl(ctx.pass, date), "_blank", "noopener");
    onClose();
  }

  // Pre-compute calendar cells outside the early return so hooks order stays stable.
  const [y, m] = month.split("-").map(Number);
  const monthFirst = new Date(Date.UTC(y, (m || 1) - 1, 1));
  const daysInMonth = new Date(Date.UTC(y, m || 1, 0)).getUTCDate();
  const leading = monthFirst.getUTCDay();
  const cells: Array<{ d: string | null; label: number | null }> = [];
  for (let i = 0; i < leading; i++) cells.push({ d: null, label: null });
  for (let i = 1; i <= daysInMonth; i++) {
    cells.push({ d: `${month}-${String(i).padStart(2, "0")}`, label: i });
  }
  const mi = months.indexOf(month);
  const ready = !!(date && selectedCard);

  // Render-time-only locals (safe behind `open`)
  const p = ctx?.pass;
  const lib = ctx?.lib;
  const attr = ctx?.attr;
  const branch = ctx?.branch;

  const fl = p ? formLabel(p.pass_form) : null;
  const vd = p && lib ? verdictLabel(p.booking_access_probe?.verdict, { network: lib.network, town: lib.town }) : null;
  const pr = p && lib ? passResidencyLabel(p.residency_restriction?.restricted, p.residency_restriction?.scope, { town: lib.town }) : null;
  const fq = p ? frequencyLimit(p.restrictions?.booking_frequency_limit) : null;
  const cs = p ? capacityStructure(p.coupon) : null;
  const cap = p?.coupon.capacity?.n;
  const capValue = cs?.total ?? cap;

  return (
    <>
      {/* Backdrop — semi-transparent, click to close. Fades. */}
      <div
        className={`drawer-backdrop${open ? " open" : ""}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      {/* Panel — fixed right, 380px, slide-in. Mounted always so transitions play on close. */}
      <aside
        className={`drawer${open ? " open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
      >
        {!open || !p || !lib || !attr ? null : (
          <>
            {/* Header */}
            <header className="drawer-head">
              <div className="drawer-title">{attr.name}</div>
              <div className="drawer-sub">
                Pickup at <strong>{branch ? `${lib.town} · ${branch.name}` : lib.town}</strong>
                <span className="drawer-net"> · {lib.network}</span>
              </div>
              <button className="drawer-x" onClick={onClose} aria-label="Close">×</button>
            </header>

            {/* Scrollable body */}
            <div className="drawer-body">
              {/* Coupon summary — the headline value prop */}
              <div className="drawer-coupon">{p.coupon.summary}</div>

              {/* Pass breakdown — per-audience policy from coupon.audience_policies */}
              <section className="drawer-section">
                <div className="section-h">Pass</div>
                {p.coupon.audience_policies && p.coupon.audience_policies.length > 0 ? (
                  p.coupon.audience_policies.map((ap, i) => {
                    const range = policyRange(ap);
                    const count = ap.count ? ` × ${ap.count}` : "";
                    return (
                      <div className="data-row sub" key={i}>
                        <span className="k">{audienceLabel(ap.audience)}{range}{count}</span>
                        <span className="v">{policyText(ap)}</span>
                      </div>
                    );
                  })
                ) : (
                  <div className="data-row sub">
                    <span className="k">Everyone</span>
                    <span className="v">{p.coupon.summary}</span>
                  </div>
                )}
              </section>

              {/* Facts */}
              <section className="drawer-section">
                <div className="data-row">
                  <span className="k">Capacity</span>
                  <span className="v">
                    {capValue ?? "—"}
                    {cs?.parts && cs.parts.length > 0 && (
                      <span className="v-note"> · {cs.parts.join(" + ")}</span>
                    )}
                  </span>
                </div>
                <div className="data-row">
                  <span className="k">Pickup</span>
                  <span className="v">{fl?.icon} {fl?.short}</span>
                </div>
                <div className="data-row">
                  <span className="k">Card</span>
                  <span className="v">{vd?.text}</span>
                </div>
                <div className="data-row">
                  <span className="k">Residency</span>
                  <span className={`v${pr?.warn ? " v-warn" : ""}`}>{pr?.text}</span>
                </div>
                <div className="data-row">
                  <span className="k">Monthly limit</span>
                  <span className="v">{fq || "—"}</span>
                </div>
              </section>

              {/* Audit row — Approve + Edit (no Book here; Book lives at foot) */}
              <section className="drawer-section drawer-audit">
                <div className="action-bar">
                  <button
                    className={`audit-btn approve${entry?.approved ? " active" : ""}`}
                    onClick={onToggleApprove}
                    title={entry?.approved ? `Approved ${new Date(entry.approved.at).toLocaleString()}` : "Mark verified"}
                  >
                    {entry?.approved ? "✓ Approved" : "✓ Approve"}
                  </button>
                  <button
                    className={`audit-btn${entry?.corrections ? " has-notes" : ""}${showEdit ? " open" : ""}`}
                    onClick={() => setShowEdit((s) => !s)}
                    title={entry?.corrections ? "Has edits — click to view" : "Add edit notes"}
                  >
                    ✎ {showEdit ? "Hide edits" : "Edit"}
                    {entry?.corrections && <span className="dot-mark" />}
                  </button>
                </div>
                {showEdit && (
                  <div className="correction-fields">
                    {AUDITABLE_FIELDS.map((f) => (
                      <div className="cf-row" key={f.key}>
                        <label className="cf-label">{f.label}</label>
                        <textarea
                          className="cf-input"
                          rows={1}
                          defaultValue={entry?.corrections?.notes[f.key] || ""}
                          onBlur={(e) => onSetCorrection(f.key, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Booking — date picker */}
              <section className="drawer-section">
                <div className="section-h">
                  Date
                  {date && <span className="section-h-pick"> · <strong>{date}</strong></span>}
                </div>
                {isAssabet ? (
                  <div className={`avail-banner ok${liveStatus === "loading" ? " loading" : ""}${liveStatus === "error" ? " err" : ""}`}>
                    {liveStatus === "loading" && "📡 Refreshing calendar…"}
                    {liveStatus === "ok"      && "📡 Live calendar"}
                    {liveStatus === "error"   && "⚠ Live fetch failed — showing snapshot"}
                    {liveStatus === "idle"    && "📡 Live calendar"}
                  </div>
                ) : (
                  <div className="avail-banner stale">
                    ⚠ Snapshot data — please confirm dates & inventory on the official site
                  </div>
                )}
                <div className="cal-nav">
                  <button onClick={() => mi > 0 && setMonth(months[mi - 1])} disabled={mi <= 0}>
                    ←
                  </button>
                  <strong>{month}</strong>
                  <button
                    onClick={() => mi < months.length - 1 && setMonth(months[mi + 1])}
                    disabled={mi >= months.length - 1}
                  >
                    →
                  </button>
                </div>
                <div className="cal-week">
                  {["S","M","T","W","T","F","S"].map((w, i) => (
                    <div key={i} className="cal-wh">{w}</div>
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
              </section>

              {/* Booking — card picker */}
              <section className="drawer-section">
                <div className="section-h">
                  Card
                  {selectedCard && (
                    <span className="section-h-pick"> · <strong>
                      {bundle.libById.get(selectedCard.library_id)?.town || selectedCard.library_id}
                    </strong></span>
                  )}
                </div>
                {/* Hint banner — explains WHY some cards are greyed. We don't
                    block the user from picking a greyed card: the verdict
                    might be wrong (probe miscalibration, recent network
                    change), or they may have another physical card not in
                    this wallet. Greyed = soft warning, not a lock. */}
                {cards.length > 0 && usableIds.size === 0 && (
                  <div className="cards-empty cards-explain">
                    {p.booking_access_probe?.verdict === "own_card_only" ? (
                      <>Our data says this pass accepts <strong>{lib.town} cards only</strong>.
                        None of your cards match — but you can still pick one and
                        try if you think we're wrong.</>
                    ) : (
                      <>Our data says this pass needs a <strong>{lib.network}</strong> network
                        card. You don't have one — but you can still pick a card
                        and try.</>
                    )}
                  </div>
                )}
                {cards.length === 0 ? (
                  <div className="cards-empty">No cards yet. Add or import from "My Cards".</div>
                ) : (
                  cards.map((c) => {
                    const usable = usableIds.has(c.id);
                    const cardLib = bundle.libById.get(c.library_id);
                    const selected = c.id === selectedCardId;
                    return (
                      <div
                        key={c.id}
                        // `disabled` here is a visual greying only — clicking
                        // still selects (see why in the explain banner above).
                        className={`card-pick${usable ? "" : " disabled"}${selected ? " selected" : ""}`}
                        onClick={() => setSelectedCardId(c.id)}
                        title={usable ? undefined : "Our data says this card likely won't be accepted — you can still try."}
                      >
                        <div className="cp-line1">
                          <span className="cp-town">{cardLib ? cardLib.town : c.library_id}</span>
                          <code className="cp-barcode">{c.card_number}</code>
                        </div>
                        {c.note && <div className="cp-line2">{c.note}</div>}
                      </div>
                    );
                  })
                )}
              </section>

              {/* Sources — each fact above pairs to a card here with the verbatim
                  evidence. Colored left rail tells the four kinds apart at a
                  glance: pass page (green) is the canonical link; coupon text
                  (gold) is the verbatim discount blurb; residency (navy) is the
                  rule under "Residency"; card probe (burgundy) is the empirical
                  card-validation result. */}
              {(p.source_url || p.coupon.source_phrase_block || p.residency_restriction?.evidence || p.booking_access_probe?.evidence) && (
                <section className="drawer-section drawer-sources">
                  <div className="section-h">Sources</div>

                  {p.source_url && (
                    <article className="src-card src-pass">
                      <header className="src-head">
                        <span className="src-label">Pass page</span>
                        <a className="src-open" href={p.source_url} target="_blank" rel="noreferrer">
                          Open ↗
                        </a>
                      </header>
                      <div className="src-host">{prettyHost(p.source_url)}</div>
                    </article>
                  )}

                  {p.coupon.source_phrase_block && (
                    <article className="src-card src-coupon">
                      <header className="src-head">
                        <span className="src-label">Coupon text</span>
                        {p.source_url && (
                          <a className="src-open" href={p.source_url} target="_blank" rel="noreferrer">
                            Open ↗
                          </a>
                        )}
                      </header>
                      <blockquote className="src-quote">{p.coupon.source_phrase_block}</blockquote>
                    </article>
                  )}

                  {p.residency_restriction?.evidence && (
                    <article className="src-card src-residency">
                      <header className="src-head">
                        <span className="src-label">Residency</span>
                        {p.residency_restriction.source && (
                          <span className="src-meta">via {p.residency_restriction.source}</span>
                        )}
                        {p.source_url && (
                          <a className="src-open" href={p.source_url} target="_blank" rel="noreferrer">
                            Open ↗
                          </a>
                        )}
                      </header>
                      <blockquote className="src-quote">{p.residency_restriction.evidence}</blockquote>
                    </article>
                  )}

                  {p.booking_access_probe?.evidence && (
                    <article className="src-card src-probe">
                      <header className="src-head">
                        <span className="src-label">Card probe</span>
                        {p.booking_access_probe.prober_card && (
                          <span className="src-meta">
                            via {p.booking_access_probe.prober_card}
                            {p.booking_access_probe.probed_date && ` · ${p.booking_access_probe.probed_date}`}
                          </span>
                        )}
                      </header>
                      <blockquote className="src-quote">{p.booking_access_probe.evidence}</blockquote>
                    </article>
                  )}
                </section>
              )}
            </div>

            {/* Sticky foot — Book button */}
            <footer className="drawer-foot">
              <button
                onClick={onBook}
                disabled={!ready}
                className="drawer-book"
                title={!date ? "Pick a date" : !selectedCard ? "Pick a card" : "Copy card & open booking page"}
              >
                Book ↗
              </button>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
