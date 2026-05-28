// LocalStorage-backed audit state: per-pass Approve flag + per-field correction
// notes. Same privacy model as the card wallet — never leaves the browser
// unless the user explicitly clicks Download.
const KEY = "coupon-map.audit.v1";

export interface AuditEntry {
  approved?: { at: string };
  corrections?: { at: string; notes: Record<string, string> };
}
export type AuditState = Record<string, AuditEntry>;

export function passKey(libId: string, slug: string): string {
  return `${libId}::${slug}`;
}

export function loadAudit(): AuditState {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as AuditState) : {};
  } catch {
    return {};
  }
}

export function saveAudit(s: AuditState) {
  localStorage.setItem(KEY, JSON.stringify(s));
}

export function downloadAudit(s: AuditState) {
  const payload = {
    exported_at: new Date().toISOString(),
    schema: "coupon-map.audit.v1",
    counts: {
      approved: Object.values(s).filter((e) => e.approved).length,
      corrections: Object.values(s).filter((e) => e.corrections).length,
      total_entries: Object.keys(s).length,
    },
    audit: s,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `coupon-map-audit-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function countApproved(s: AuditState): number {
  return Object.values(s).filter((e) => e.approved).length;
}
export function countCorrections(s: AuditState): number {
  return Object.values(s).filter((e) => e.corrections && Object.keys(e.corrections.notes).length > 0).length;
}

// Auditable structured-data fields the correction form lets the user annotate.
// Each entry's note travels through as-is to the downloaded JSON.
export const AUDITABLE_FIELDS: Array<{ key: string; label: string }> = [
  { key: "discount", label: "折扣 (DISC)" },
  { key: "capacity", label: "人数上限" },
  { key: "pass_form", label: "领取方式 (Email/Pickup/Pickup&return)" },
  { key: "verdict", label: "卡限制 (system 层)" },
  { key: "residency", label: "取券居住地" },
  { key: "frequency_limit", label: "月领限制" },
  { key: "other", label: "其他 (自由备注)" },
];
