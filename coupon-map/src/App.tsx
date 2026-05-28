import { useEffect, useState } from "react";
import type { DataBundle } from "./data/types";
import { loadAll } from "./data/load";
import Matrix from "./pages/Matrix";
import MyCards from "./pages/MyCards";

type Tab = "matrix" | "cards";

export default function App() {
  const [tab, setTab] = useState<Tab>("matrix");
  const [bundle, setBundle] = useState<DataBundle | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    loadAll().then(setBundle).catch((e) => setErr(String(e?.stack || e?.message || e)));
  }, []);

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
      </header>
      <main className="app-body">
        {tab === "matrix" && <Matrix bundle={bundle} />}
        {tab === "cards" && <MyCards bundle={bundle} />}
      </main>
    </div>
  );
}
