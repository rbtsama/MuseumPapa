// Three-state rendering helper. Has-value / genuinely-absent / parse-error must
// be visually distinct and must never be conflated, so a render bug can never
// be misread as a data bug.
import type { ReactNode } from "react";

export function present(node: ReactNode) {
  return <span className="text-ink-2">{node}</span>;
}
export function absent(reason = "暂无") {
  return <span className="text-ink-3 italic opacity-70">{reason}</span>;
}
export function errored(raw: unknown, field?: string) {
  // Intentionally loud. Never paint an error as a blank.
  const t = field ? `${field}: ${JSON.stringify(raw)}` : JSON.stringify(raw);
  return (
    <span className="text-rd" title={t}>
      ⚠ 解析异常
    </span>
  );
}
