import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@heroui/react";
import type { Attraction, Branch, DataBundle, Library, Pass } from "../data/types";
import { type AuditState, passKey } from "../store/audit";
import {
  adultPrice,
  compactHours,
  eligibilityLabel,
  formLabel,
  priceLine,
  reservationFlag,
  simpleDiscount,
} from "../lib/derive";
import BookingDrawer, { type DrawerCtx } from "../components/BookingDrawer";

interface Props {
  bundle: DataBundle;
  audit: AuditState;
  updateAudit: (u: (s: AuditState) => AuditState) => void;
}

// Per-network super-header tint (newspaper palette, low-saturation muted hues).
// Sized 5 → 5 networks; the green stays the anchor (Minuteman is the largest
// group), the others read as related-but-distinct without breaking the editorial
// look. Falls back to deep green for any unknown network.
const NETWORK_COLOR: Record<string, string> = {
  Minuteman: "#1B5740", // main deep green
  NOBLE:     "#2A4A6B", // newsprint navy
  MVLC:      "#8C6018", // gold
  OCLN:      "#8C2A1E", // burgundy
  MBLN:      "#4A4845", // dark ink
};

// One matrix column = either a library (institutional) or a branch sub-column
// (pickup-location only — policy is verified identical across branches).
export type Col =
  | { kind: "lib"; lib: Library; branches: Branch[]; netStart: boolean }
  | { kind: "branch"; lib: Library; branch: Branch; idx: number; total: number };

function useColumns(bundle: DataBundle, expanded: Set<string>) {
  return useMemo(() => {
    const cols: Col[] = [];
    const groups: Array<{ network: string; span: number }> = [];
    for (const g of bundle.networks) {
      const startLen = cols.length;
      let first = true;
      for (const lib of g.libraries) {
        const branches = bundle.branchesByLib.get(lib.id) ?? [];
        cols.push({ kind: "lib", lib, branches, netStart: first });
        first = false;
        if (branches.length > 1 && expanded.has(lib.id)) {
          branches.forEach((branch, idx) =>
            cols.push({ kind: "branch", lib, branch, idx, total: branches.length })
          );
        }
      }
      groups.push({ network: g.network, span: cols.length - startLen });
    }
    return { cols, groups };
  }, [bundle, expanded]);
}

export default function Matrix({ bundle, audit, updateAudit }: Props) {
  // Toggle the Approve flag for one pass key.
  const toggleApprove = (key: string) =>
    updateAudit((s) => {
      const cur = s[key] || {};
      if (cur.approved) {
        const { approved: _a, ...rest } = cur;
        const next = { ...s };
        if (Object.keys(rest).length === 0) delete next[key];
        else next[key] = rest;
        return next;
      }
      return { ...s, [key]: { ...cur, approved: { at: new Date().toISOString() } } };
    });

  // Write/clear a correction note for one field of one pass.
  const setCorrection = (key: string, field: string, note: string) =>
    updateAudit((s) => {
      const cur = s[key] || {};
      const notes = { ...(cur.corrections?.notes || {}) };
      if (note.trim() === "") delete notes[field];
      else notes[field] = note;
      const next = { ...s };
      if (Object.keys(notes).length === 0) {
        const { corrections: _c, ...rest } = cur;
        if (Object.keys(rest).length === 0) delete next[key];
        else next[key] = rest;
      } else {
        next[key] = { ...cur, corrections: { at: new Date().toISOString(), notes } };
      }
      return next;
    });

  const [expandedLibs, setExpandedLibs] = useState<Set<string>>(new Set());
  const toggleExpand = (libId: string) =>
    setExpandedLibs((prev) => {
      const next = new Set(prev);
      next.has(libId) ? next.delete(libId) : next.add(libId);
      return next;
    });
  const { cols, groups } = useColumns(bundle, expandedLibs);

  // ── filters ─────────────────────────────────────────────────────────
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string>("");
  const [form, setForm] = useState<string>("");
  const [verdictF, setVerdictF] = useState<string>("");
  const [residencyF, setResidencyF] = useState<string>("");

  const categories = useMemo(() => {
    const s = new Set<string>();
    bundle.attractions.forEach((a) => a.categories?.forEach((c) => s.add(c)));
    return Array.from(s).sort();
  }, [bundle]);

  // Row filter only over attractions; cell-form/verdict filters mask cells.
  const rows = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return bundle.attractions
      .filter((a) => (category ? (a.categories || []).includes(category) : true))
      .filter((a) => (ql ? a.name.toLowerCase().includes(ql) || a.slug.includes(ql) : true))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [bundle, q, category]);

  // Drawer state — one slide-in panel replaces the old popover+modal chain.
  // Clicking another cell while one is open: null-out first so the close
  // animation plays, then mount the new ctx after ~220ms.
  const [drawerCtx, setDrawerCtx] = useState<DrawerCtx | null>(null);
  const switchTimer = useRef<number | null>(null);
  function openDrawer(ctx: DrawerCtx) {
    if (switchTimer.current) {
      window.clearTimeout(switchTimer.current);
      switchTimer.current = null;
    }
    if (drawerCtx) {
      setDrawerCtx(null);
      switchTimer.current = window.setTimeout(() => {
        setDrawerCtx(ctx);
        switchTimer.current = null;
      }, 220);
    } else {
      setDrawerCtx(ctx);
    }
  }
  function closeDrawer() {
    if (switchTimer.current) {
      window.clearTimeout(switchTimer.current);
      switchTimer.current = null;
    }
    setDrawerCtx(null);
  }

  function cellKey(a: Attraction, l: Library) {
    return `${a.slug}::${l.id}`;
  }
  function cellMatch(p: Pass) {
    if (form && p.pass_form !== form) return false;
    if (verdictF && p.booking_access_probe?.verdict !== verdictF) return false;
    if (residencyF && (p.residency_restriction?.restricted || "unknown") !== residencyF) return false;
    return true;
  }

  // 92px gives town names ("Wakefield", "Wilmington") + 💳 icon enough room
  // without cutting at the right edge. Branches share the same width.
  const cellTemplate = `260px ${cols.map(() => "92px").join(" ")}`;

  // Crosshair hover — light up the hovered row's row-head and the hovered
  // column's town header via direct DOM mutation, so the user can orient
  // themselves on this wide matrix without us re-rendering 5700 cells.
  const matrixRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const matrix = matrixRef.current;
    if (!matrix) return;
    let lastRow: HTMLElement | null = null;
    let lastCol: HTMLElement | null = null;
    const onOver = (e: Event) => {
      const t = (e.target as HTMLElement).closest("[data-row], [data-col]") as HTMLElement | null;
      if (!t) return;
      const row = t.getAttribute("data-row");
      const col = t.getAttribute("data-col");
      if (lastRow && lastRow.getAttribute("data-row") !== row) {
        lastRow.classList.remove("row-active"); lastRow = null;
      }
      if (lastCol && lastCol.getAttribute("data-col") !== col) {
        lastCol.classList.remove("col-active"); lastCol = null;
      }
      if (row && !lastRow) {
        const rh = matrix.querySelector(`.mx-row-head[data-row="${CSS.escape(row)}"]`) as HTMLElement | null;
        if (rh) { rh.classList.add("row-active"); lastRow = rh; }
      }
      if (col && !lastCol) {
        const ch = matrix.querySelector(`.mx-town[data-col="${col}"]`) as HTMLElement | null;
        if (ch) { ch.classList.add("col-active"); lastCol = ch; }
      }
    };
    const onLeave = () => {
      if (lastRow) { lastRow.classList.remove("row-active"); lastRow = null; }
      if (lastCol) { lastCol.classList.remove("col-active"); lastCol = null; }
    };
    matrix.addEventListener("mouseover", onOver);
    matrix.addEventListener("mouseleave", onLeave);
    return () => {
      matrix.removeEventListener("mouseover", onOver);
      matrix.removeEventListener("mouseleave", onLeave);
    };
  }, [cols.length, rows.length]);

  return (
    <div>
      <div className="filter-bar">
        <input
          type="text"
          placeholder="Search attraction…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 200 }}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={form} onChange={(e) => setForm(e.target.value)}>
          <option value="">All pickup methods</option>
          <option value="digital_email">✉ Email</option>
          <option value="physical_coupon">★ Pickup</option>
          <option value="physical_circ">★★ Pickup &amp; return</option>
        </select>
        <select value={verdictF} onChange={(e) => setVerdictF(e.target.value)}>
          <option value="">All card scopes</option>
          <option value="network_open">🟢 Network</option>
          <option value="own_card_only">🔴 Own card only</option>
          <option value="not_verified">⚪ Not verified</option>
          <option value="ambiguous">🟠 Ambiguous</option>
        </select>
        <select value={residencyF} onChange={(e) => setResidencyF(e.target.value)}>
          <option value="">All residency</option>
          <option value="no">No residency requirement</option>
          <option value="yes">Residency required</option>
          <option value="unknown">Residency unknown</option>
        </select>
        <span className="count">
          {rows.length}/{bundle.attractions.length} attractions · {cols.length} libs · {bundle.passes.length} passes
        </span>
      </div>

      <div className="matrix-scroll">
        <div ref={matrixRef} className="matrix" style={{ gridTemplateColumns: cellTemplate }}>
          {/* row 1: corner + network groups */}
          <div className="mx-corner">Attractions × Libraries (by network)</div>
          {groups.map((g) => (
            <div
              key={g.network}
              className="mx-net"
              style={{ gridColumn: `span ${g.span}`, background: NETWORK_COLOR[g.network] || "#1B5740" }}
              title={`${g.network} (${g.span} 馆)`}
            >
              {g.network} · {g.span}
            </div>
          ))}

          {/* row 2: corner-2 + town headers (+ optional branch sub-headers) */}
          <div className="mx-corner-2">
            {rows.length} × {bundle.libraries.length}
            {expandedLibs.size > 0 ? ` (${expandedLibs.size} expanded)` : ""}
          </div>
          {cols.map((c, ci) =>
            c.kind === "lib"
              ? (() => {
                  const l = c.lib;
                  const e = eligibilityLabel(l.card_eligibility, { network: l.network, town: l.town });
                  const expanded = expandedLibs.has(l.id);
                  const multi = c.branches.length > 1;
                  const cls = `mx-town${c.netStart ? " net-start" : ""}`;
                  return (
                    <Popover key={`lib:${l.id}:${ci}`} placement="bottom" showArrow>
                      <PopoverTrigger>
                        <div className={cls} data-col={String(ci)}>
                          {l.town}
                          {multi && (
                            <button
                              className="expand-btn"
                              onClick={(ev) => {
                                ev.stopPropagation();
                                toggleExpand(l.id);
                              }}
                              title={expanded ? `收起 ${c.branches.length} 个分馆` : `展开 ${c.branches.length} 个分馆`}
                            >
                              {expanded ? "−" : "+"}
                              {c.branches.length}
                            </button>
                          )}
                        </div>
                      </PopoverTrigger>
                      <PopoverContent>
                        <div className="popover-v2">
                          <header className="pv-header">
                            <div className="pv-title">{l.name}</div>
                            {multi && (
                              <span className="pv-badge">{c.branches.length} branches</span>
                            )}
                          </header>

                          <div className="pv-body">
                            {/* LEFT — Hours */}
                            <section className="pv-col">
                              <div className="pv-h">Hours</div>
                              {l.hours ? (
                                <ul className="hours-compact">
                                  {compactHours(l.hours).map((r) => (
                                    <li key={r.days}>
                                      <span className="hc-d">{r.days}</span>
                                      <span className={`hc-v${r.value === "Closed" ? " hc-closed" : ""}`}>{r.value}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : l.hours_note ? (
                                <div className="block-note">{l.hours_note}</div>
                              ) : (
                                <div style={{ color: "#8a877f" }}>—</div>
                              )}
                            </section>

                            {/* RIGHT — Basic info (network membership + residency + address) */}
                            <section className="pv-col">
                              <div className="pv-h">Basic info</div>
                              <ul className="basic-info">
                                <li>
                                  <span className="bi-k">Town</span>
                                  <span className="bi-v">{l.town}</span>
                                </li>
                                <li>
                                  <span className="bi-k">Network</span>
                                  <span className="bi-v">{l.network}</span>
                                </li>
                                <li>
                                  <span className="bi-k">Resident</span>
                                  <span className={`bi-v${e.warn ? " v-attn" : ""}`}>{e.text}</span>
                                </li>
                                {l.address && (
                                  <li>
                                    <span className="bi-k">Address</span>
                                    <span className="bi-v">
                                      {l.address.street && <div>{l.address.street}</div>}
                                      <div>
                                        {[l.address.city, l.address.state, l.address.zip].filter(Boolean).join(", ")}
                                      </div>
                                    </span>
                                  </li>
                                )}
                                {l.card_page && (
                                  <li>
                                    <span className="bi-k">Card page</span>
                                    <a className="bi-v pv-link" href={l.card_page} target="_blank" rel="noreferrer">
                                      {prettyHost(l.card_page)} ↗
                                    </a>
                                  </li>
                                )}
                              </ul>
                            </section>
                          </div>

                          <div className="pv-sources">
                            <EvidenceSection
                              items={[
                                { label: "Card page", source: l.card_page || null },
                                l._evidence?.card_eligibility
                                  ? {
                                      label: "Library card eligibility",
                                      quote: l._evidence.card_eligibility.block || l._evidence.card_eligibility.evidence || null,
                                      source: l._evidence.card_eligibility.source || null,
                                    }
                                  : { label: "" },
                                l._evidence?.hours
                                  ? {
                                      label: "Hours",
                                      quote: l._evidence.hours.block || l._evidence.hours.evidence || null,
                                      source: l._evidence.hours.source || null,
                                    }
                                  : l._evidence?.hours_note
                                  ? {
                                      label: "Hours (varies)",
                                      quote: l._evidence.hours_note.evidence || null,
                                      source: l._evidence.hours_note.source || null,
                                    }
                                  : { label: "" },
                              ]}
                            />
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  );
                })()
              : (() => {
                  // branch sub-column header
                  const b = c.branch;
                  return (
                    <Popover key={`br:${b.id}:${ci}`} placement="bottom" showArrow>
                      <PopoverTrigger>
                        <div className="mx-town branch-head" data-col={String(ci)}>
                          {b.name}
                        </div>
                      </PopoverTrigger>
                      <PopoverContent>
                        <div className="popover-v2">
                          <header className="pv-header">
                            <div className="pv-title">{b.name}</div>
                            <span className="pv-badge">Branch</span>
                            <div className="pv-meta">
                              <span>{c.lib.name}</span>
                              <span className="pv-sep">·</span>
                              <span>{c.lib.town}</span>
                              <span className="pv-sep">·</span>
                              <span>{c.lib.network}</span>
                            </div>
                          </header>

                          {(c.lib.hours || c.lib.hours_note || b.code || b.geo) && (
                            <div className="pv-body">
                              {(c.lib.hours || c.lib.hours_note) && (
                                <section className="pv-col">
                                  <div className="pv-h">Hours (institution)</div>
                                  {c.lib.hours ? (
                                    <ul className="hours-compact">
                                      {compactHours(c.lib.hours).map((r) => (
                                        <li key={r.days}>
                                          <span className="hc-d">{r.days}</span>
                                          <span className={`hc-v${r.value === "Closed" ? " hc-closed" : ""}`}>{r.value}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  ) : (
                                    <div className="block-note">{c.lib.hours_note}</div>
                                  )}
                                </section>
                              )}
                              {(b.code || b.geo) && (
                                <section className="pv-col">
                                  <div className="pv-h">Branch info</div>
                                  {b.code && <div>Code: <strong>{b.code}</strong></div>}
                                  {b.geo && (
                                    <div style={{ color: "#4a4845", fontVariantNumeric: "tabular-nums" }}>
                                      {b.geo.lat.toFixed(4)}, {b.geo.lon.toFixed(4)}
                                    </div>
                                  )}
                                </section>
                              )}
                            </div>
                          )}

                          <div className="pv-sources">
                          <EvidenceSection
                            items={[
                              { label: "Card page", source: c.lib.card_page || null },
                              c.lib._evidence?.card_eligibility
                                ? {
                                    label: "Library card eligibility",
                                    quote: c.lib._evidence.card_eligibility.block || c.lib._evidence.card_eligibility.evidence || null,
                                    source: c.lib._evidence.card_eligibility.source || null,
                                  }
                                : { label: "" },
                              c.lib._evidence?.hours
                                ? {
                                    label: "Institution hours",
                                    quote: c.lib._evidence.hours.block || c.lib._evidence.hours.evidence || null,
                                    source: c.lib._evidence.hours.source || null,
                                  }
                                : c.lib._evidence?.hours_note
                                ? {
                                    label: "Institution hours (varies)",
                                    quote: c.lib._evidence.hours_note.evidence || null,
                                    source: c.lib._evidence.hours_note.source || null,
                                  }
                                : { label: "" },
                            ]}
                          />
                          </div>
                        </div>
                      </PopoverContent>
                    </Popover>
                  );
                })()
          )}

          {/* data rows */}
          {rows.map((a) => {
            const adult = adultPrice(a);
            const resFlag = reservationFlag(a);
            return (
              <RowFragment
                key={a.slug}
                attr={a}
                cols={cols}
                bundle={bundle}
                cellMatch={cellMatch}
                drawerKey={drawerCtx ? `${drawerCtx.attr.slug}::${drawerCtx.lib.id}${drawerCtx.branch ? `::${drawerCtx.branch.id}` : ""}` : null}
                adult={adult}
                resFlag={resFlag}
                audit={audit}
                onCellClick={(lib, branch, pass) => openDrawer({ attr: a, lib, branch, pass })}
              />
            );
          })}
        </div>
      </div>

      <BookingDrawer
        bundle={bundle}
        ctx={drawerCtx}
        entry={drawerCtx ? audit[passKey(drawerCtx.lib.id, drawerCtx.attr.slug)] : undefined}
        onClose={closeDrawer}
        onToggleApprove={() => drawerCtx && toggleApprove(passKey(drawerCtx.lib.id, drawerCtx.attr.slug))}
        onSetCorrection={(field, note) => drawerCtx && setCorrection(passKey(drawerCtx.lib.id, drawerCtx.attr.slug), field, note)}
      />
    </div>
  );
}

interface RowProps {
  attr: Attraction;
  cols: Col[];
  bundle: DataBundle;
  cellMatch: (p: Pass) => boolean;
  drawerKey: string | null;
  adult: number | null;
  resFlag: ReturnType<typeof reservationFlag>;
  audit: AuditState;
  onCellClick: (lib: Library, branch: Branch | null, pass: Pass) => void;
}

function RowFragment({ attr, cols, bundle, cellMatch, drawerKey, adult, resFlag, audit, onCellClick }: RowProps) {
  return (
    <>
      <Popover placement="right-start" showArrow>
        <PopoverTrigger>
          <div className="mx-row-head" data-row={attr.slug}>
            <div className="attr-name">{attr.name}</div>
            <div className="attr-meta">
              {attr.categories?.slice(0, 2).join(" · ")} · ${adult ?? "—"}
              {resFlag.need && (
                <span style={{ color: "#D97706", marginLeft: 6 }}>⚠预约</span>
              )}
            </div>
          </div>
        </PopoverTrigger>
        <PopoverContent>
          <AttractionDetail a={attr} />
        </PopoverContent>
      </Popover>

      {cols.map((c, ci) => {
        const l = c.kind === "lib" ? c.lib : c.lib;
        const key =
          c.kind === "lib"
            ? `${attr.slug}::${l.id}`
            : `${attr.slug}::${l.id}::${c.branch.id}`;
        const p = bundle.passByPair.get(`${attr.slug}::${l.id}`);
        const startCls = c.kind === "lib" && c.netStart ? " net-start" : "";

        // Pass cell — plain clickable div. Click opens the right-side drawer
        // (no per-cell popover state, no modal — the drawer is a single
        // top-level panel driven by drawerCtx).
        if (!p) return <div key={key} className={`mx-cell empty${startCls}`} data-row={attr.slug} data-col={String(ci)} />;
        const masked = !cellMatch(p);
        const branch = c.kind === "branch" ? c.branch : null;
        const pkey = passKey(p.library_id, p.attraction_slug);
        const entry = audit[pkey];
        const isActive = drawerKey === key;
        return (
          <div
            key={key}
            className={`mx-cell${startCls}${isActive ? " drawer-active" : ""}`}
            style={masked ? { opacity: 0.18 } : undefined}
            data-row={attr.slug}
            data-col={String(ci)}
            onClick={() => !masked && onCellClick(l, branch, p)}
            role="button"
            tabIndex={masked ? -1 : 0}
            onKeyDown={(e) => {
              if (!masked && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                onCellClick(l, branch, p);
              }
            }}
          >
            <CellGlyph p={p} lib={l} approved={!!entry?.approved} hasCorrection={!!entry?.corrections} />
          </div>
        );
      })}
    </>
  );
}

// Evidence row: a labelled quote + an optional clickable source URL. Renders
// the bottom half of every popover so each derived fact in the top half has
// the raw source the user can verify against.
interface EvidenceItem {
  label: string;
  quote?: string | null;
  source?: string | null;
}
function prettyHost(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "") + (u.pathname && u.pathname !== "/" ? u.pathname : "");
  } catch {
    return url;
  }
}
function EvidenceSection({ items }: { items: EvidenceItem[] }) {
  const visible = items.filter((i) => i.quote || i.source);
  if (visible.length === 0) return null;
  return (
    <div className="evidence">
      <div className="section-h">Sources</div>
      {visible.map((it, i) => (
        <div className="ev-item" key={i}>
          {(it.label || it.source) && (
            <div className="ev-head">
              {it.label && <span className="ev-label">{it.label}</span>}
              {it.source && (
                <a className="ev-link" href={it.source} target="_blank" rel="noreferrer">
                  Open ↗
                </a>
              )}
            </div>
          )}
          {it.quote && <div className="ev-quote">{it.quote}</div>}
        </div>
      ))}
    </div>
  );
}

function CellGlyph({ p, lib, approved, hasCorrection }: { p: Pass; lib: Library; approved?: boolean; hasCorrection?: boolean }) {
  const fl = formLabel(p.pass_form);
  const verdict = p.booking_access_probe?.verdict;
  const ownOnly = verdict === "own_card_only";
  const networkOpen = verdict === "network_open";
  const residency = p.residency_restriction?.restricted;
  const residencyScope = p.residency_restriction?.scope;
  // Line 2: Network (default) when any same-network card works; the town name
  // in orange when restricted to this library's own card; em-dash when not
  // yet verified or ambiguous.
  const networkText = ownOnly ? lib.town : networkOpen ? "Network" : verdict === "ambiguous" ? "Network?" : "—";
  const networkColor = ownOnly ? "#D97706" : networkOpen ? "#1B5740" : "#B5B2A8";
  // Line 3: residency only when there IS a restriction (yes). Otherwise hidden.
  let residencyText: string | null = null;
  if (residency === "yes") {
    // 🏠 icon already conveys "lives here"; just print the locality.
    residencyText = residencyScope === "ma" ? "MA" : lib.town;
  }
  return (
    <div className="glyph">
      {approved && <span className="approved-badge" title="已 Approve · 数据已人工认证" />}
      {hasCorrection && !approved && <span className="correction-badge" title="有纠错备注 · 待 review" />}
      <div className="glyph-l1">
        <span className="amount">{simpleDiscount(p.coupon)}</span>
        {fl.cellIcon && <span className="form-icon-solid">{fl.cellIcon}</span>}
      </div>
      <div className="glyph-l2" style={{ color: networkColor }}>
        <span className="line-icon">💳</span> {networkText}
      </div>
      {residencyText && (
        <div className="glyph-l3">
          <span className="line-icon">🏠</span> {residencyText}
        </div>
      )}
    </div>
  );
}

function AttractionDetail({ a }: { a: Attraction }) {
  const reservationText: Record<string, string> = {
    walk_in_ok: "Walk-in OK",
    required: "Reservation required",
    recommended: "Reservation recommended",
  };
  const resRaw = a.reservation?.required || "unknown";
  const resText = reservationText[resRaw] || resRaw;
  const needsRes = resRaw !== "walk_in_ok" && resRaw !== "unknown";
  const adult = adultPrice(a);
  const addr = a.address ? [a.address.street, a.address.city, a.address.state, a.address.zip].filter(Boolean).join(", ") : null;

  // Build the inline meta chips. Categories (up to 2) + adult price + reservation
  // hint — everything the user sees at a glance before deciding whether to dig
  // into the popover body.
  const chips: ReactNode[] = [];
  (a.categories || []).slice(0, 2).forEach((c, i) => {
    if (i > 0) chips.push(<span key={`s-cat-${i}`} className="pv-sep">·</span>);
    chips.push(<span key={`cat-${i}`}>{c}</span>);
  });
  if (adult != null) {
    if (chips.length) chips.push(<span key="s-pr" className="pv-sep">·</span>);
    chips.push(<span key="pr">Adult ${adult}</span>);
  }
  if (resRaw !== "unknown") {
    if (chips.length) chips.push(<span key="s-rv" className="pv-sep">·</span>);
    chips.push(<span key="rv" className={needsRes ? "v-attn" : ""}>{resText}</span>);
  }

  const hasBody = !!a.hours || !!a.hours_note || (a.prices && a.prices.length > 0);
  return (
    <div className="popover-v2">
      <header className="pv-header">
        <div className="pv-title">{a.name}</div>
        <div className="pv-meta">
          {chips}
          {a.website && (
            <a className="pv-link" href={a.website} target="_blank" rel="noreferrer">
              {prettyHost(a.website)} ↗
            </a>
          )}
        </div>
      </header>

      {hasBody && (
        <div className={`pv-body${a.prices && a.prices.length > 0 ? "" : " single"}`}>
          {/* Hours */}
          {(a.hours || a.hours_note) && (
            <section className="pv-col">
              <div className="pv-h">Hours</div>
              {a.hours ? (
                <ul className="hours-compact">
                  {compactHours(a.hours).map((r) => (
                    <li key={r.days}>
                      <span className="hc-d">{r.days}</span>
                      <span className={`hc-v${r.value === "Closed" ? " hc-closed" : ""}`}>{r.value}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="block-note">{a.hours_note}</div>
              )}
            </section>
          )}

          {/* Tickets */}
          {a.prices && a.prices.length > 0 && (
            <section className="pv-col">
              <div className="pv-h">Tickets</div>
              <div className="pv-tickets">
                {a.prices.map((p, i) => {
                  const pl = priceLine(p);
                  return (
                    <div key={i}>
                      <span className="pv-aud">{pl.label}</span>
                      <span className={`pv-price${pl.isFree ? " v-free" : ""}`}>{pl.value}</span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      )}

      {(addr || a.website) && (
        <div className="pv-address">
          {addr ? <span>{addr}</span> : <span style={{ opacity: 0.5 }}>Address unknown</span>}
          {a.website && (
            <a className="pv-link" href={a.website} target="_blank" rel="noreferrer">
              {prettyHost(a.website)} ↗
            </a>
          )}
        </div>
      )}

      <div className="pv-sources">
      <EvidenceSection
        items={[
          {
            label: "Website",
            source: a.website || (Array.isArray(a.sources) && (a.sources as string[])[0]) || null,
          },
          a.prices && a.prices.length > 0
            ? {
                label: `Price · ${a.prices[0].audience}`,
                quote: a.prices[0].source_block || a.prices[0].source_phrase || null,
                source: a.prices[0].source_url || a.website || null,
              }
            : { label: "" },
          a.reservation?.required
            ? {
                label: "Reservation policy",
                quote: a.reservation?.source_block || a.reservation?.source_phrase || a.reservation?.notes || null,
                source: a.reservation?.source_url || a.reservation?.booking_url || a.reservation?.pass_holder_url || null,
              }
            : { label: "" },
          a._evidence?.hours
            ? {
                label: "Hours",
                quote: a._evidence.hours.block || a._evidence.hours.evidence || null,
                source: a._evidence.hours.source || null,
              }
            : a._evidence?.hours_note
            ? {
                label: "Hours (varies)",
                quote: a._evidence.hours_note.evidence || null,
                source: a._evidence.hours_note.source || null,
              }
            : { label: "" },
        ]}
      />
      </div>
    </div>
  );
}

