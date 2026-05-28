import { useEffect, useState } from "react";
import type { DataBundle } from "./data/types";
import { loadAll } from "./data/load";
import Matrix from "./pages/Matrix";
import MyCards from "./pages/MyCards";
import {
  type AuditState,
  countApproved,
  countCorrections,
  downloadAudit,
  loadAudit,
  saveAudit,
} from "./store/audit";

type Tab = "matrix" | "cards";

export default function App() {
  const [tab, setTab] = useState<Tab>("matrix");
  const [bundle, setBundle] = useState<DataBundle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [audit, setAuditState] = useState<AuditState>({});

  useEffect(() => {
    loadAll().then(setBundle).catch((e) => setErr(String(e?.stack || e?.message || e)));
    setAuditState(loadAudit());
  }, []);

  // Single mutator everyone uses. Persists to localStorage and re-renders.
  const updateAudit = (updater: (s: AuditState) => AuditState) => {
    setAuditState((prev) => {
      const next = updater(prev);
      saveAudit(next);
      return next;
    });
  };

  if (err)
    return (
      <div className="fullscreen error">
        <div>
          <strong>数据加载失败(保真校验未通过)</strong>
          {"\n\n"}
          {err}
        </div>
      </div>
    );
  if (!bundle) return <div className="fullscreen">加载数据中…</div>;

  const nApproved = countApproved(audit);
  const nCorrections = countCorrections(audit);

  return (
    <div>
      <header className="app-header">
        <h1>Coupon Map</h1>
        <div className={`tab ${tab === "matrix" ? "active" : ""}`} onClick={() => setTab("matrix")}>
          优惠总览
        </div>
        <div className={`tab ${tab === "cards" ? "active" : ""}`} onClick={() => setTab("cards")}>
          我的卡
        </div>
        <div className="header-spacer" />
        <div className="audit-counter" title="已 Approve / 有纠错备注 的 pass 条数">
          ✅ {nApproved} · 📝 {nCorrections}
        </div>
        <button
          className="header-btn"
          onClick={() => downloadAudit(audit)}
          disabled={nApproved === 0 && nCorrections === 0}
          title="下载 Approve + 纠错备注 为 JSON"
        >
          ⬇ 下载校验数据
        </button>
      </header>
      <main className="app-body">
        {tab === "matrix" && <Matrix bundle={bundle} audit={audit} updateAudit={updateAudit} />}
        {tab === "cards" && <MyCards bundle={bundle} />}
      </main>
    </div>
  );
}
