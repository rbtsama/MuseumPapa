import { useEffect, useMemo, useRef, useState } from "react";
import { Modal, ModalBody, ModalContent, Popover, PopoverContent, PopoverTrigger } from "@heroui/react";
import type { Attraction, Branch, DataBundle, Library, Pass } from "../data/types";
import { AUDITABLE_FIELDS, type AuditState, passKey } from "../store/audit";
import {
  adultPrice,
  audienceLabel,
  capacityStructure,
  eligibilityLabel,
  formLabel,
  frequencyLimit,
  passResidencyLabel,
  policyRange,
  policyText,
  reservationFlag,
  simpleDiscount,
  verdictLabel,
} from "../lib/derive";
import BookingWizard from "../components/BookingWizard";

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

  // Wizard state
  const [bookCtx, setBookCtx] = useState<{ attr: Attraction; lib: Library; pass: Pass } | null>(null);

  // Cell detail popover (inline) — show on click
  const [openKey, setOpenKey] = useState<string | null>(null);

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
                        <div className="detail-card">
                          <div className="card-subtitle">{l.name}</div>

                          <div className="data-section">
                            <div className="data-row">
                              <span className="k">Town</span>
                              <span className="v">{l.town}</span>
                            </div>
                            <div className="data-row">
                              <span className="k">Network</span>
                              <span className="v">{l.network}</span>
                            </div>
                            <div className="data-row">
                              <span className="k">Eligibility</span>
                              <span className={`v${e.warn ? " v-warn" : ""}`}>{e.text}</span>
                            </div>
                            {multi && (
                              <div className="data-row">
                                <span className="k">Branches</span>
                                <span className="v">{c.branches.length}</span>
                              </div>
                            )}
                          </div>

                          {l.hours ? (
                            <div className="data-section">
                              <div className="section-h">Hours</div>
                              <div className="hours-grid">
                                {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const).map((d) => (
                                  <div key={d}>
                                    <span className="hours-d">{d.slice(0, 3)}</span>
                                    <span className="hours-v">{l.hours?.[d] || "—"}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : l.hours_note ? (
                            <div className="data-section">
                              <div className="section-h">Hours</div>
                              <div className="block-note">{l.hours_note}</div>
                            </div>
                          ) : null}

                          {(l.address || l.card_page) && (
                            <div className="data-section compact">
                              {l.address && (
                                <div className="addr">
                                  {[l.address.street, l.address.city, l.address.state, l.address.zip].filter(Boolean).join(", ")}
                                </div>
                              )}
                              {l.card_page && (
                                <a className="ext-link" href={l.card_page} target="_blank" rel="noreferrer">{prettyHost(l.card_page)} ↗</a>
                              )}
                            </div>
                          )}
                          <EvidenceSection
                            items={[
                              { label: "Card page", source: l.card_page || null },
                              l._evidence?.card_eligibility
                                ? {
                                    label: "Eligibility",
                                    quote: l._evidence.card_eligibility.evidence || null,
                                    source: l._evidence.card_eligibility.source || null,
                                  }
                                : { label: "" },
                              l._evidence?.hours
                                ? {
                                    label: "Hours",
                                    quote: l._evidence.hours.evidence || null,
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
                        <div className="detail-card">
                          <div className="card-subtitle">{b.name} · branch of {c.lib.name}</div>

                          <div className="data-section">
                            <div className="data-row"><span className="k">Town</span><span className="v">{c.lib.town}</span></div>
                            <div className="data-row"><span className="k">Network</span><span className="v">{c.lib.network}</span></div>
                            {b.code && <div className="data-row"><span className="k">Code</span><span className="v">{b.code}</span></div>}
                            {b.geo && (
                              <div className="data-row">
                                <span className="k">Geo</span>
                                <span className="v">{b.geo.lat.toFixed(4)}, {b.geo.lon.toFixed(4)}</span>
                              </div>
                            )}
                          </div>

                          {c.lib.hours ? (
                            <div className="data-section">
                              <div className="section-h">Hours (institution)</div>
                              <div className="hours-grid">
                                {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const).map((d) => (
                                  <div key={d}>
                                    <span className="hours-d">{d.slice(0, 3)}</span>
                                    <span className="hours-v">{c.lib.hours?.[d] || "—"}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : c.lib.hours_note ? (
                            <div className="data-section">
                              <div className="section-h">Hours (institution)</div>
                              <div className="block-note">{c.lib.hours_note}</div>
                            </div>
                          ) : null}
                          <EvidenceSection
                            items={[
                              { label: "Card page", source: c.lib.card_page || null },
                              c.lib._evidence?.card_eligibility
                                ? {
                                    label: "Eligibility",
                                    quote: c.lib._evidence.card_eligibility.evidence || null,
                                    source: c.lib._evidence.card_eligibility.source || null,
                                  }
                                : { label: "" },
                              c.lib._evidence?.hours
                                ? {
                                    label: "Institution hours",
                                    quote: c.lib._evidence.hours.evidence || null,
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
                openKey={openKey}
                setOpenKey={setOpenKey}
                adult={adult}
                resFlag={resFlag}
                audit={audit}
                onToggleApprove={toggleApprove}
                onSetCorrection={setCorrection}
                onBook={(lib, pass) => setBookCtx({ attr: a, lib, pass })}
              />
            );
          })}
        </div>
      </div>

      <Modal
        isOpen={!!bookCtx}
        onOpenChange={(o) => !o && setBookCtx(null)}
        size="3xl"
      >
        <ModalContent>
          <ModalBody style={{ padding: 0 }}>
            {bookCtx && (
              <BookingWizard
                bundle={bundle}
                attraction={bookCtx.attr}
                pass={bookCtx.pass}
                lib={bookCtx.lib}
                onClose={() => setBookCtx(null)}
              />
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </div>
  );
}

interface RowProps {
  attr: Attraction;
  cols: Col[];
  bundle: DataBundle;
  cellMatch: (p: Pass) => boolean;
  openKey: string | null;
  setOpenKey: (k: string | null) => void;
  adult: number | null;
  resFlag: ReturnType<typeof reservationFlag>;
  audit: AuditState;
  onToggleApprove: (key: string) => void;
  onSetCorrection: (key: string, field: string, note: string) => void;
  onBook: (lib: Library, pass: Pass) => void;
}

function RowFragment({ attr, cols, bundle, cellMatch, openKey, setOpenKey, adult, resFlag, audit, onToggleApprove, onSetCorrection, onBook }: RowProps) {
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

        // Both lib and branch cells render identically — branches are peer
        // pickup-locations, not subordinates. The popover header carries the
        // location label so the user sees the actual pickup point.
        if (!p) return <div key={key} className={`mx-cell empty${startCls}`} data-row={attr.slug} data-col={String(ci)} />;
        const masked = !cellMatch(p);
        const branch = c.kind === "branch" ? c.branch : null;
        const locTitle = branch ? `${l.town} · ${branch.name}` : l.town;
        const pkey = passKey(p.library_id, p.attraction_slug);
        const entry = audit[pkey];
        return (
          <Popover
            key={key}
            placement="bottom"
            showArrow
            isOpen={openKey === key}
            onOpenChange={(o) => setOpenKey(o ? key : null)}
          >
            <PopoverTrigger>
              <div
                className={`mx-cell${startCls}`}
                style={masked ? { opacity: 0.18 } : undefined}
                data-row={attr.slug}
                data-col={String(ci)}
              >
                <CellGlyph p={p} lib={l} approved={!!entry?.approved} hasCorrection={!!entry?.corrections} />
              </div>
            </PopoverTrigger>
            <PopoverContent>
              <CellDetail
                p={p}
                attr={attr}
                lib={l}
                branch={branch}
                entry={entry}
                onToggleApprove={() => onToggleApprove(pkey)}
                onSetCorrection={(field, note) => onSetCorrection(pkey, field, note)}
                onBook={() => {
                  setOpenKey(null);
                  onBook(l, p);
                }}
              />
            </PopoverContent>
          </Popover>
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
          {it.label && <div className="ev-label">{it.label}</div>}
          {it.quote && <div className="ev-quote">{it.quote}</div>}
          {it.source && (
            <a className="ev-link" href={it.source} target="_blank" rel="noreferrer">
              {prettyHost(it.source)} ↗
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function CellAuditRow({
  entry,
  onToggleApprove,
  onSetCorrection,
}: {
  entry?: { approved?: { at: string }; corrections?: { at: string; notes: Record<string, string> } };
  onToggleApprove: () => void;
  onSetCorrection: (field: string, note: string) => void;
}) {
  const [showEdit, setShowEdit] = useState(false);
  return (
    <>
      <div className="audit-row">
        <button
          className={`audit-btn${entry?.corrections ? " has-notes" : ""}${showEdit ? " open" : ""}`}
          onClick={() => setShowEdit((s) => !s)}
        >
          <span className="ico">✎</span> Edit
          {entry?.corrections && <span className="dot-mark" />}
        </button>
        <button
          className={`audit-btn approve${entry?.approved ? " active" : ""}`}
          onClick={onToggleApprove}
        >
          <span className="ico">✓</span> {entry?.approved ? "Approved" : "Approve"}
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
    </>
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
    walk_in_ok: "Walk-in",
    required: "Reservation required",
    recommended: "Reservation recommended",
  };
  const res = a.reservation?.required ? (reservationText[a.reservation.required] || a.reservation.required) : "Unknown";
  const addr = a.address ? [a.address.street, a.address.city, a.address.state, a.address.zip].filter(Boolean).join(", ") : null;
  return (
    <div className="detail-card">
      <div className="card-subtitle">{a.name}</div>

      {a.prices && a.prices.length > 0 && (
        <div className="data-section">
          <div className="section-h">Tickets</div>
          {a.prices.map((p, i) => {
            const range = p.age_range && p.age_range.min != null
              ? ` ${p.age_range.min}${p.age_range.max != null ? `–${p.age_range.max}` : "+"}`
              : "";
            return (
              <div key={i} className="data-row sub">
                <span className="k">{p.audience}{range}</span>
                <span className="v">{p.price == null ? "—" : `$${p.price}`}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className="data-section">
        <div className="data-row">
          <span className="k">Reservation</span>
          <span className="v">{res}</span>
        </div>
      </div>

      {a.hours ? (
        <div className="data-section">
          <div className="section-h">Hours</div>
          <div className="hours-grid">
            {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const).map((d) => (
              <div key={d}>
                <span className="hours-d">{d.slice(0, 3)}</span>
                <span className="hours-v">{a.hours?.[d] || "—"}</span>
              </div>
            ))}
          </div>
        </div>
      ) : a.hours_note ? (
        <div className="data-section">
          <div className="section-h">Hours</div>
          <div className="block-note">{a.hours_note}</div>
        </div>
      ) : null}

      {(addr || a.website) && (
        <div className="data-section compact">
          {addr && <div className="addr">{addr}</div>}
          {a.website && (
            <a className="ext-link" href={a.website} target="_blank" rel="noreferrer">{prettyHost(a.website)} ↗</a>
          )}
        </div>
      )}
      <EvidenceSection
        items={[
          {
            label: "Website",
            source: a.website || (Array.isArray(a.sources) && (a.sources as string[])[0]) || null,
          },
          a.prices && a.prices.length > 0
            ? {
                label: `Price · ${a.prices[0].audience}`,
                quote: a.prices[0].source_phrase || null,
                source: a.website || null,
              }
            : { label: "" },
          a.reservation?.required
            ? {
                label: "Reservation policy",
                quote: a.reservation?.source_phrase || a.reservation?.notes || null,
                source: a.reservation?.booking_url || a.reservation?.pass_holder_url || null,
              }
            : { label: "" },
          a._evidence?.hours
            ? {
                label: "Hours",
                quote: a._evidence.hours.evidence || null,
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
  );
}

function CellDetail({
  p,
  attr,
  lib,
  branch,
  entry,
  onToggleApprove,
  onSetCorrection,
  onBook,
}: {
  p: Pass;
  attr: Attraction;
  lib: Library;
  branch?: Branch | null;
  entry?: { approved?: { at: string }; corrections?: { at: string; notes: Record<string, string> } };
  onToggleApprove: () => void;
  onSetCorrection: (field: string, note: string) => void;
  onBook: () => void;
}) {
  const fl = formLabel(p.pass_form);
  const vd = verdictLabel(p.booking_access_probe?.verdict, { network: lib.network, town: lib.town });
  const pr = passResidencyLabel(p.residency_restriction?.restricted, p.residency_restriction?.scope, { town: lib.town });
  const fq = frequencyLimit(p.restrictions?.booking_frequency_limit);
  const cap = p.coupon.capacity?.n;
  const cs = capacityStructure(p.coupon);
  const capValue = cs.total ?? cap;
  return (
    <div className="detail-card">
      <div className="card-subtitle">
        {attr.name} · {branch ? `${lib.town} · ${branch.name}` : lib.town} · {lib.network}
      </div>

      <button onClick={onBook} className="book-cta">
        <span className="book-cta-arrow">↗</span> Book now
      </button>

      {/* Discount — plain row group with sub-rows for each audience. */}
      <div className="data-section">
        <div className="section-h">Discount</div>
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
      </div>

      {/* Other facts — one row each. */}
      <div className="data-section">
        <div className="data-row">
          <span className="k">Capacity</span>
          <span className="v">
            {capValue ?? "—"}
            {cs.parts && cs.parts.length > 0 && (
              <span className="v-note"> · {cs.parts.join(" + ")}</span>
            )}
          </span>
        </div>
        <div className="data-row">
          <span className="k">Pickup</span>
          <span className="v">{fl.icon} {fl.short}</span>
        </div>
        <div className="data-row">
          <span className="k">Card</span>
          <span className="v">{vd.text}</span>
        </div>
        <div className="data-row">
          <span className="k">Residency</span>
          <span className={`v${pr.warn ? " v-warn" : ""}`}>{pr.text}</span>
        </div>
        <div className="data-row">
          <span className="k">Monthly limit</span>
          <span className="v">{fq || "—"}</span>
        </div>
        {branch && branch.geo && (
          <div className="data-row">
            <span className="k">Pickup geo</span>
            <span className="v">{branch.geo.lat.toFixed(4)}, {branch.geo.lon.toFixed(4)}</span>
          </div>
        )}
      </div>

      {/* Audit — Edit on the left, Approve on the right. Edit toggles an inline
          field-by-field form below the row (form is a sibling node so it never
          pushes Approve to a second line). */}
      <CellAuditRow
        entry={entry}
        onToggleApprove={onToggleApprove}
        onSetCorrection={onSetCorrection}
      />

      <EvidenceSection
        items={[
          { label: "Pass page", source: p.source_url || null },
          p.coupon.source_phrase_block
            ? { label: "Coupon text", quote: p.coupon.source_phrase_block, source: p.source_url || null }
            : { label: "" },
          p.residency_restriction?.evidence
            ? {
                label: `Residency (${p.residency_restriction.source || "—"})`,
                quote: p.residency_restriction.evidence || null,
                source: p.source_url || null,
              }
            : { label: "" },
          p.booking_access_probe?.evidence
            ? {
                label:
                  `Card probe` +
                  (p.booking_access_probe.prober_card ? ` (via ${p.booking_access_probe.prober_card})` : "") +
                  (p.booking_access_probe.probed_date ? ` · ${p.booking_access_probe.probed_date}` : ""),
                quote: p.booking_access_probe.evidence || null,
                source: p.source_url || null,
              }
            : { label: "" },
        ]}
      />
    </div>
  );
}
