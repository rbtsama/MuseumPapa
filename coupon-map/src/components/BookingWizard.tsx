import { useEffect, useMemo, useState } from "react";
import type { Attraction, DataBundle, Library, Pass } from "../data/types";
import { formLabel, matchCards, verdictLabel } from "../lib/derive";
import { loadCards } from "../store/cards";

interface Props {
  bundle: DataBundle;
  attraction: Attraction;
  preselectLib: Library | null;
  onClose: () => void;
}

type Step = 1 | 2 | 3;

// Aggregate availability for one attraction across all its passes.
// A date is "available" if ANY library's pass for this attraction is available.
function aggregateAvail(passes: Pass[]) {
  const all = new Map<string, { available: number; booked: number; closed: number }>();
  for (const p of passes) {
    if (!p.availability) continue;
    for (const [d, st] of Object.entries(p.availability)) {
      const v = all.get(d) || { available: 0, booked: 0, closed: 0 };
      if (st === "available") v.available++;
      else if (st === "booked") v.booked++;
      else if (st === "closed") v.closed++;
      all.set(d, v);
    }
  }
  return all;
}

export default function BookingWizard({ bundle, attraction, preselectLib, onClose }: Props) {
  // All passes for this attraction
  const passesForAttr = useMemo(
    () => bundle.passes.filter((p) => p.attraction_slug === attraction.slug),
    [bundle, attraction]
  );
  const passByLib = useMemo(() => {
    const m = new Map<string, Pass>();
    for (const p of passesForAttr) m.set(p.library_id, p);
    return m;
  }, [passesForAttr]);
  const agg = useMemo(() => aggregateAvail(passesForAttr), [passesForAttr]);

  const [step, setStep] = useState<Step>(1);
  const [date, setDate] = useState<string | null>(null);
  const [libId, setLibId] = useState<string | null>(preselectLib?.id || null);
  const cards = useMemo(() => loadCards(), []);

  // Build month range from availability data span
  const dates = useMemo(() => Array.from(agg.keys()).sort(), [agg]);
  const today = new Date().toISOString().slice(0, 10);
  const months = useMemo(() => {
    const ms = new Set<string>();
    dates.forEach((d) => ms.add(d.slice(0, 7)));
    return Array.from(ms).sort();
  }, [dates]);
  const [month, setMonth] = useState(() => months[0] || today.slice(0, 7));

  useEffect(() => {
    if (!month && months.length) setMonth(months[0]);
  }, [months, month]);

  function statusFor(d: string): "available" | "booked" | "closed" | "none" {
    const v = agg.get(d);
    if (!v) return "none";
    if (v.available > 0) return "available";
    if (v.booked > 0) return "booked";
    return "closed";
  }

  // ── Step 1: calendar ──
  if (step === 1) {
    const [y, m] = month.split("-").map(Number);
    const first = new Date(Date.UTC(y, m - 1, 1));
    const dim = new Date(Date.UTC(y, m, 0)).getUTCDate();
    const leading = first.getUTCDay(); // 0=Sun
    const cells: Array<{ d: string | null; label: number | null }> = [];
    for (let i = 0; i < leading; i++) cells.push({ d: null, label: null });
    for (let i = 1; i <= dim; i++) {
      const ds = `${month}-${String(i).padStart(2, "0")}`;
      cells.push({ d: ds, label: i });
    }
    const mi = months.indexOf(month);
    return (
      <div className="wizard">
        <h3>① 选日期 — {attraction.name}</h3>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <button onClick={() => mi > 0 && setMonth(months[mi - 1])} disabled={mi <= 0} style={navBtn}>
            ← {months[mi - 1] || ""}
          </button>
          <strong>{month}</strong>
          <button onClick={() => mi < months.length - 1 && setMonth(months[mi + 1])} disabled={mi >= months.length - 1} style={navBtn}>
            {months[mi + 1] || ""} →
          </button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, fontSize: 12 }}>
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((w) => (
            <div key={w} style={{ textAlign: "center", color: "#4a4845", padding: 4 }}>{w}</div>
          ))}
          {cells.map((c, i) => {
            if (!c.d) return <div key={i} />;
            const st = statusFor(c.d);
            const past = c.d < today;
            const v = agg.get(c.d);
            const palette: Record<string, { bg: string; fg: string; clickable: boolean }> = {
              available: { bg: "#C4DDCF", fg: "#1B5740", clickable: true },
              booked: { bg: "#FDF1E2", fg: "#8C6018", clickable: false },
              closed: { bg: "#ECEAE4", fg: "#4A4845", clickable: false },
              none: { bg: "#FAFAF7", fg: "#B5B2A8", clickable: false },
            };
            const p = palette[st];
            const disabled = past || !p.clickable;
            return (
              <button
                key={c.d}
                disabled={disabled}
                onClick={() => {
                  setDate(c.d!);
                  setStep(2);
                }}
                style={{
                  background: p.bg,
                  color: p.fg,
                  border: "1px solid #D0CEC6",
                  borderRadius: 4,
                  padding: "6px 0 4px",
                  fontSize: 12,
                  cursor: disabled ? "default" : "pointer",
                  opacity: past ? 0.35 : 1,
                  textAlign: "center",
                }}
                title={v ? `available:${v.available} booked:${v.booked} closed:${v.closed}` : "无数据"}
              >
                <div style={{ fontWeight: 600 }}>{c.label}</div>
                <div style={{ fontSize: 10 }}>{v ? `${v.available}馆` : "—"}</div>
              </button>
            );
          })}
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: "#4a4845" }}>
          绿=至少一馆当日可领 · 黄=全部已被订 · 灰=馆休息 · 数字=当日可领馆数
        </div>
      </div>
    );
  }

  // ── Step 2: pick library ──
  if (step === 2 && date) {
    const rows = bundle.networks
      .flatMap((g) => g.libraries.filter((l) => passByLib.has(l.id)))
      .map((l) => {
        const p = passByLib.get(l.id)!;
        const av = p.availability?.[date];
        return { lib: l, pass: p, avail: av };
      })
      .sort((a, b) => {
        const av = (x: typeof a) => (x.avail === "available" ? 0 : x.avail === "booked" ? 1 : 2);
        const d = av(a) - av(b);
        return d !== 0 ? d : a.lib.town.localeCompare(b.lib.town);
      });

    return (
      <div className="wizard">
        <h3>② 选图书馆 — {date}</h3>
        <button onClick={() => setStep(1)} style={navBtn}>← 改日期</button>
        <div className="lib-pick" style={{ marginTop: 10 }}>
          {rows.map(({ lib, pass, avail }) => {
            const usable = avail === "available";
            const fl = formLabel(pass.pass_form);
            const vd = verdictLabel(pass.booking_access_probe?.verdict);
            const { exact, network } = matchCards(cards, pass, bundle.libById);
            const hasCard = exact.length > 0 || network.length > 0;
            const chosen = exact[0] || network[0];
            return (
              <div key={lib.id} className={`pick ${usable ? "" : "dim"}`}>
                <span className="town">{lib.town}</span>
                <span style={{ fontSize: 11, color: "#4a4845" }}>{lib.network}</span>
                <span className="form">{fl.icon} {fl.short}</span>
                <span className="summary">{pass.coupon.summary}</span>
                <span style={{ fontSize: 11 }} title={vd.text}>{vd.dot}</span>
                <span style={{ fontSize: 11, color: usable ? "#1B5740" : "#8C6018" }}>
                  {avail === "available" ? "当日可领" : avail === "booked" ? "已被订" : avail === "closed" ? "休息" : "无数据"}
                </span>
                <span className={`card ${hasCard ? "" : "no"}`}>
                  {hasCard ? (
                    <>
                      <span title={exact.length ? "本馆卡" : "同 network 卡"}>
                        {exact.length ? "✓本馆卡" : "✓同 network 卡"}
                      </span>
                      <code style={{ background: "#ECEAE4", padding: "1px 4px", borderRadius: 3 }}>
                        {chosen.card_number}
                      </code>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(chosen.card_number);
                        }}
                        style={btnTinyInline}
                      >
                        复制
                      </button>
                      <button
                        disabled={!usable}
                        onClick={() => {
                          setLibId(lib.id);
                          setStep(3);
                        }}
                        style={{ ...btnPrimaryInline, opacity: usable ? 1 : 0.4 }}
                      >
                        下一步
                      </button>
                    </>
                  ) : (
                    <span>⚠ 你没可用卡</span>
                  )}
                </span>
              </div>
            );
          })}
          {rows.length === 0 && <div>该景点没有任何馆提供 pass。</div>}
        </div>
      </div>
    );
  }

  // ── Step 3: confirm + open external booking page ──
  if (step === 3 && date && libId) {
    const lib = bundle.libById.get(libId)!;
    const pass = passByLib.get(libId)!;
    const { exact, network } = matchCards(cards, pass, bundle.libById);
    const chosen = exact[0] || network[0];
    const url = pass.source_url || attraction.reservation?.booking_url || lib.pass_page || lib.card_page || "";
    return (
      <div className="wizard">
        <h3>③ 确认 · 复制卡号 · 跳转</h3>
        <button onClick={() => setStep(2)} style={navBtn}>← 改图书馆</button>
        <div style={{ marginTop: 12, padding: 12, background: "#EAF1EE", borderRadius: 6 }}>
          <div className="row"><strong>景点</strong> {attraction.name}</div>
          <div className="row"><strong>日期</strong> {date}</div>
          <div className="row"><strong>取券馆</strong> {lib.town} ({lib.network})</div>
          <div className="row"><strong>优惠</strong> {pass.coupon.summary}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <strong>卡号</strong>{" "}
            <code style={{ background: "#FAFAF7", padding: "2px 6px", borderRadius: 3 }}>
              {chosen?.card_number || "(无卡)"}
            </code>{" "}
            {chosen && (
              <button onClick={() => navigator.clipboard.writeText(chosen.card_number)} style={btnTinyInline}>
                复制
              </button>
            )}
          </div>
        </div>
        <div style={{ marginTop: 12, padding: 10, borderLeft: "3px solid #8C6018", background: "#F4EFE8", fontSize: 12 }}>
          外部预定页无法自动预填:打开后请在该页面手动选择 <strong>{date}</strong>,
          并粘贴卡号即可完成预定。
        </div>
        <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
          <a href={url} target="_blank" rel="noreferrer" style={{ ...btnPrimaryInline, textDecoration: "none", display: "inline-block" }}>
            打开预定页 ↗
          </a>
          <button onClick={onClose} style={btnGhostInline}>
            关闭
          </button>
        </div>
      </div>
    );
  }

  return null;
}

const navBtn: React.CSSProperties = {
  padding: "3px 8px",
  background: "#FAFAF7",
  color: "#1a1917",
  border: "1px solid #D0CEC6",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 11,
};
const btnPrimaryInline: React.CSSProperties = {
  padding: "4px 10px",
  background: "#1B5740",
  color: "#FAFAF7",
  border: "none",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 11,
  fontWeight: 600,
};
const btnGhostInline: React.CSSProperties = {
  padding: "4px 10px",
  background: "#FAFAF7",
  color: "#1a1917",
  border: "1px solid #D0CEC6",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 11,
};
const btnTinyInline: React.CSSProperties = {
  padding: "1px 6px",
  background: "#EAF1EE",
  color: "#1B5740",
  border: "1px solid #C4DDCF",
  borderRadius: 3,
  cursor: "pointer",
  fontSize: 10,
};
