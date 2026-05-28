import { useMemo, useState } from "react";
import { Modal, ModalBody, ModalContent, ModalHeader, Popover, PopoverContent, PopoverTrigger } from "@heroui/react";
import type { Attraction, Branch, DataBundle, Library, Pass } from "../data/types";
import {
  adultPrice,
  audienceLabel,
  availabilitySummary,
  eligibilityLabel,
  formLabel,
  frequencyLimit,
  passResidencyLabel,
  policyRange,
  policyText,
  reservationFlag,
  verdictLabel,
} from "../lib/derive";
import BookingWizard from "../components/BookingWizard";

interface Props { bundle: DataBundle }

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

export default function Matrix({ bundle }: Props) {
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
  const [onlyAvail, setOnlyAvail] = useState(false);

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
  const [bookAttr, setBookAttr] = useState<Attraction | null>(null);
  const [bookLib, setBookLib] = useState<Library | null>(null);

  // Cell detail popover (inline) — show on click
  const [openKey, setOpenKey] = useState<string | null>(null);

  function cellKey(a: Attraction, l: Library) {
    return `${a.slug}::${l.id}`;
  }
  function cellMatch(p: Pass) {
    if (form && p.pass_form !== form) return false;
    if (verdictF && p.booking_access_probe?.verdict !== verdictF) return false;
    if (onlyAvail) {
      const av = availabilitySummary(p.availability);
      if (av !== "has_avail") return false;
    }
    return true;
  }

  // Lib cols 78px; branch sub-cols 64px (subdued; policy identical to parent).
  const cellTemplate = `260px ${cols.map((c) => (c.kind === "lib" ? "78px" : "64px")).join(" ")}`;

  return (
    <div>
      <div className="filter-bar">
        <input
          type="text"
          placeholder="搜景点名/slug…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 200 }}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">所有分类</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={form} onChange={(e) => setForm(e.target.value)}>
          <option value="">所有领取方式</option>
          <option value="digital_email">✉ Email</option>
          <option value="physical_coupon">☆ Pickup</option>
          <option value="physical_circ">☆☆ Pickup &amp; return</option>
        </select>
        <select value={verdictF} onChange={(e) => setVerdictF(e.target.value)}>
          <option value="">所有卡限制</option>
          <option value="network_open">🟢 network 任意卡</option>
          <option value="own_card_only">🔴 仅本馆卡</option>
          <option value="not_verified">⚪ 未验证</option>
          <option value="ambiguous">🟠 存疑</option>
        </select>
        <label style={{ display: "flex", gap: 4, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={onlyAvail} onChange={(e) => setOnlyAvail(e.target.checked)} />
          仅有库存
        </label>
        <span className="count">
          景点 {rows.length}/{bundle.attractions.length} · 馆 {cols.length} · pass 总 {bundle.passes.length}
        </span>
      </div>

      <div className="matrix-scroll">
        <div className="matrix" style={{ gridTemplateColumns: cellTemplate }}>
          {/* row 1: corner + network groups */}
          <div className="mx-corner">景点 \ 图书馆 (按 network)</div>
          {groups.map((g) => (
            <div
              key={g.network}
              className="mx-net"
              style={{ gridColumn: `span ${g.span}` }}
              title={`${g.network} (${g.span} 馆)`}
            >
              {g.network} · {g.span}
            </div>
          ))}

          {/* row 2: corner-2 + town headers (+ optional branch sub-headers) */}
          <div className="mx-corner-2">
            {rows.length} 景 × {bundle.libraries.length} 馆
            {expandedLibs.size > 0 ? ` (展开 ${expandedLibs.size})` : ""}
          </div>
          {cols.map((c, ci) =>
            c.kind === "lib"
              ? (() => {
                  const l = c.lib;
                  const e = eligibilityLabel(l.card_eligibility);
                  const expanded = expandedLibs.has(l.id);
                  const multi = c.branches.length > 1;
                  const cls = `mx-town${c.netStart ? " net-start" : ""}`;
                  return (
                    <Popover key={`lib:${l.id}:${ci}`} placement="bottom" showArrow>
                      <PopoverTrigger>
                        <div className={cls} title={`${l.name} (${l.network})`}>
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
                          <h4>{l.name}</h4>
                          <div className="row">
                            <span className="k">Town / Network</span>
                            <span>
                              {l.town} · {l.network}
                            </span>
                          </div>
                          <div className="row">
                            <span className="k">办卡 residency</span>
                            <span title={e.tooltip} style={{ color: e.warn ? "#8c2a1e" : "#1a1917" }}>
                              {e.text}
                            </span>
                          </div>
                          {l.address && (
                            <div className="row">
                              <span className="k">地址</span>
                              <span>
                                {[l.address.street, l.address.city, l.address.state, l.address.zip]
                                  .filter(Boolean)
                                  .join(", ")}
                              </span>
                            </div>
                          )}
                          {l.card_page && (
                            <div className="row">
                              <span className="k">办卡页</span>
                              <a href={l.card_page} target="_blank" rel="noreferrer">
                                打开
                              </a>
                            </div>
                          )}
                          <div className="row">
                            <span className="k">营业时间</span>
                            <span style={{ color: "#4a4845", fontStyle: "italic" }}>暂无数据 (v0.2)</span>
                          </div>
                          {multi && (
                            <div className="row" style={{ display: "block", marginTop: 4 }}>
                              <span className="k">分馆 ({c.branches.length})</span>
                              <span style={{ fontSize: 11, color: "#4a4845" }}>
                                政策与主馆一致(已校验:1015/1015 passes `available_at_branches="all"`);
                                分馆维度仅 pickup-location 差异。点击 town 右侧 [+] 展开列。
                              </span>
                            </div>
                          )}
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
                        <div className="mx-town branch-head" title={`${b.name} (${c.lib.name} 分馆)`}>
                          ↳{b.name}
                        </div>
                      </PopoverTrigger>
                      <PopoverContent>
                        <div className="detail-card">
                          <h4>
                            {c.lib.town} · <span style={{ fontWeight: 400 }}>{b.name}</span>
                          </h4>
                          <div className="row">
                            <span className="k">所属</span>
                            <span>{c.lib.name}</span>
                          </div>
                          {b.code && (
                            <div className="row">
                              <span className="k">code</span>
                              <span>{b.code}</span>
                            </div>
                          )}
                          {b.geo && (
                            <div className="row">
                              <span className="k">geo</span>
                              <span>
                                {b.geo.lat.toFixed(4)}, {b.geo.lon.toFixed(4)}
                              </span>
                            </div>
                          )}
                          <div className="row" style={{ display: "block", marginTop: 6, color: "#8C6018", fontSize: 11 }}>
                            ⓘ 此列为分馆 pickup-location;policy/coupon/availability 与主馆 {c.lib.town} 完全一致(已校验)。
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
                openKey={openKey}
                setOpenKey={setOpenKey}
                adult={adult}
                resFlag={resFlag}
                onBook={(lib) => {
                  setBookAttr(a);
                  setBookLib(lib);
                }}
              />
            );
          })}
        </div>
      </div>

      <Modal
        isOpen={!!bookAttr}
        onOpenChange={(o) => !o && (setBookAttr(null), setBookLib(null))}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalContent>
          <ModalHeader>预定预检 — {bookAttr?.name}</ModalHeader>
          <ModalBody>
            {bookAttr && (
              <BookingWizard
                bundle={bundle}
                attraction={bookAttr}
                preselectLib={bookLib}
                onClose={() => {
                  setBookAttr(null);
                  setBookLib(null);
                }}
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
  onBook: (lib: Library) => void;
}

function RowFragment({ attr, cols, bundle, cellMatch, openKey, setOpenKey, adult, resFlag, onBook }: RowProps) {
  return (
    <>
      <Popover placement="right-start" showArrow>
        <PopoverTrigger>
          <div className="mx-row-head" title={attr.slug}>
            <div className="attr-name">{attr.name}</div>
            <div className="attr-meta">
              {attr.categories?.slice(0, 2).join(" · ")} · ${adult ?? "—"}{" "}
              <span style={{ color: resFlag.tone === "or" ? "#D97706" : "#1B5740" }}>
                {resFlag.need ? "⚠预约" : "✅walk-in"}
              </span>
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

        // Branch sub-column: subdued ditto marker, no own pass facts.
        if (c.kind === "branch") {
          if (!p) return <div key={key} className={`mx-cell branch empty`} />;
          return (
            <Popover key={key} placement="bottom" showArrow>
              <PopoverTrigger>
                <div className="mx-cell branch" title={`${c.branch.name} 分馆 — 凭证同 ${l.town} 主馆`}>
                  ↳
                </div>
              </PopoverTrigger>
              <PopoverContent>
                <div className="detail-card">
                  <h4>
                    {l.town} · <span style={{ fontWeight: 400 }}>{c.branch.name}</span>
                  </h4>
                  <div className="row" style={{ display: "block", color: "#8C6018", fontSize: 11 }}>
                    凭证 / 折扣 / 库存 与主馆 {l.town} 完全一致(已校验);此分馆仅作 pickup-location 选项。
                  </div>
                  {c.branch.geo && (
                    <div className="row">
                      <span className="k">geo</span>
                      <span>
                        {c.branch.geo.lat.toFixed(4)}, {c.branch.geo.lon.toFixed(4)}
                      </span>
                    </div>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <button
                      onClick={() => onBook(l)}
                      style={{
                        padding: "5px 10px",
                        background: "#1B5740",
                        color: "#FAFAF7",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    >
                      去预定 (主馆入口)
                    </button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          );
        }

        // lib column (the institutional cell)
        if (!p) return <div key={key} className={`mx-cell empty${startCls}`} />;
        const masked = !cellMatch(p);
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
                title={`${attr.name} × ${l.town}`}
              >
                <CellGlyph p={p} />
              </div>
            </PopoverTrigger>
            <PopoverContent>
              <CellDetail
                p={p}
                attr={attr}
                lib={l}
                onBook={() => {
                  setOpenKey(null);
                  onBook(l);
                }}
              />
            </PopoverContent>
          </Popover>
        );
      })}
    </>
  );
}

function CellGlyph({ p }: { p: Pass }) {
  const fl = formLabel(p.pass_form);
  const av = availabilitySummary(p.availability);
  const dot = av === "has_avail" ? "#1B5740" : av === "all_booked" ? "#D97706" : "#B5B2A8";
  const ownOnly = p.booking_access_probe?.verdict === "own_card_only";
  return (
    <>
      <span className="summary">{p.coupon.summary}</span>
      <br />
      <span className="form-icon">{fl.icon}</span>
      <span className="dot-avail" style={{ background: dot }} />
      {ownOnly && <span className="own-only">本</span>}
    </>
  );
}

function AttractionDetail({ a }: { a: Attraction }) {
  return (
    <div className="detail-card">
      <h4>{a.name}</h4>
      {a.categories && <div className="row"><span className="k">分类</span><span>{a.categories.join(" / ")}</span></div>}
      {a.address && (
        <div className="row">
          <span className="k">地址</span>
          <span>{[a.address.street, a.address.city, a.address.state, a.address.zip].filter(Boolean).join(", ")}</span>
        </div>
      )}
      {a.hours ? (
        <div className="row" style={{ display: "block" }}>
          <div className="k">营业时间</div>
          <div style={{ fontSize: 11 }}>
            {(["monday","tuesday","wednesday","thursday","friday","saturday","sunday"] as const).map((d) => (
              <div key={d}>
                {d.slice(0, 3)}: {a.hours?.[d] || "—"}
              </div>
            ))}
          </div>
        </div>
      ) : a.hours_note ? (
        <div className="row" style={{ display: "block" }}>
          <div className="k">营业时间</div>
          <div style={{ fontSize: 11, color: "#8C6018" }}>⚠ {a.hours_note}</div>
        </div>
      ) : (
        <div className="row">
          <span className="k">营业时间</span>
          <span style={{ color: "#4a4845", fontStyle: "italic" }}>暂无数据</span>
        </div>
      )}
      {a.prices && a.prices.length > 0 && (
        <div className="row" style={{ display: "block" }}>
          <div className="k">票价(原价)</div>
          <div style={{ fontSize: 11 }}>
            {a.prices.map((p, i) => (
              <div key={i}>
                {p.audience}: {p.price == null ? "—" : `$${p.price}`}
                {p.age_range && p.age_range.min != null
                  ? ` (${p.age_range.min}${p.age_range.max != null ? `-${p.age_range.max}` : "+"})`
                  : ""}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="row">
        <span className="k">是否需预约</span>
        <span>{a.reservation?.required || "未知"}</span>
      </div>
      {a.website && (
        <div className="row">
          <span className="k">官网</span>
          <a href={a.website} target="_blank" rel="noreferrer">打开</a>
        </div>
      )}
    </div>
  );
}

function CellDetail({
  p,
  attr,
  lib,
  onBook,
}: {
  p: Pass;
  attr: Attraction;
  lib: Library;
  onBook: () => void;
}) {
  const fl = formLabel(p.pass_form);
  const vd = verdictLabel(p.booking_access_probe?.verdict);
  const pr = passResidencyLabel(p.residency_restriction?.restricted);
  const fq = frequencyLimit(p.restrictions?.booking_frequency_limit);
  const cap = p.coupon.capacity?.n;
  return (
    <div className="detail-card">
      <h4>
        {attr.name} <span style={{ color: "#4a4845", fontWeight: 400 }}>×</span> {lib.town}
        <span style={{ color: "#4a4845", fontWeight: 400, fontSize: 11 }}> ({lib.network})</span>
      </h4>
      <div className="row"><span className="k">折扣</span><span style={{ color: "#1B5740", fontWeight: 600 }}>{p.coupon.summary}</span></div>
      <div className="row"><span className="k">人数上限</span><span>{cap ? `up to ${cap} ${p.coupon.capacity?.kind || "people"}` : "—"}</span></div>
      <div className="row"><span className="k">领取方式</span><span title={fl.tooltip}>{fl.icon} {fl.short}</span></div>
      <div className="row"><span className="k">卡限制</span><span title={p.booking_access_probe?.evidence || ""}>{vd.dot} {vd.text}</span></div>
      <div className="row"><span className="k">取券 residency</span><span style={{ color: pr.warn ? "#8c2a1e" : "#1a1917" }}>{pr.text}</span></div>
      <div className="row"><span className="k">每月领取限制</span><span>{fq || "不限"}</span></div>
      {p.coupon.audience_policies && p.coupon.audience_policies.length > 0 ? (
        <div className="breakdown">
          <div className="k" style={{ marginBottom: 3, fontWeight: 600, color: "#8c6018" }}>
            分人群折扣
          </div>
          {p.coupon.audience_policies.map((ap, i) => (
            <div className="pol" key={i}>
              <span>
                {audienceLabel(ap.audience)}
                {policyRange(ap)}
                {ap.count ? ` × ${ap.count}` : ""}
              </span>
              <span className="v">{policyText(ap)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="row">
          <span className="k">分人群折扣</span>
          <span style={{ color: "#4a4845", fontStyle: "italic" }}>未细分</span>
        </div>
      )}
      <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
        <button
          onClick={onBook}
          style={{
            padding: "6px 12px",
            background: "#1B5740",
            color: "#FAFAF7",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          去预定
        </button>
        {p.source_url && (
          <a
            href={p.source_url}
            target="_blank"
            rel="noreferrer"
            style={{
              padding: "6px 12px",
              border: "1px solid #D0CEC6",
              borderRadius: 4,
              color: "#1a1917",
              textDecoration: "none",
              fontSize: 12,
            }}
          >
            源页面 ↗
          </a>
        )}
      </div>
    </div>
  );
}
