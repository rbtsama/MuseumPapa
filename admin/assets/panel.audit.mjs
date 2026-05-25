// Pure audit-record + form-control logic for the admin panel. No DOM, no network.
export const CARD_ELIGIBILITY = ["ma_resident","town_resident","town_or_works","network","none","unknown"];
export const PASS_PICKUP = ["same_as_card","ma_resident","town_resident","town_cardholder_only","network","walkin_for_nonresidents","none","unknown"];
export const COUPON_FORM = ["free","percent-off","dollar-off","per-person-price","bogo","discount"];
export const CAPACITY_KIND = ["people","vehicle","ticket","unspecified"];
export const VISITOR_RESIDENCY = ["ma_resident","town_resident","none","unknown"];
export const RESERVATION_REQUIRED = ["none","timed_entry","walk_in_ok"];
export const RESIDENCY_RESTRICTED = ["yes","no","unknown"];
export const RESIDENCY_SCOPE = ["town","ma"];
export const PASS_FORM = ["digital_email","physical_coupon","physical_circ"];

export const CORRECTION_KIND = ["conclusion_wrong","value_wrong"]; // 结论错 / 值错
export const ROOT_CAUSE = ["extraction_error","unobtainable"];     // 取错了 / 取不到

export function auditTarget(kind, id, field) { return `${kind}:${id}:${field}`; }

export function buildRecord({ kind, id, field, status, correction_kind = null,
                             root_cause = null, corrected_value, note = "" }) {
  if (status === "corrected" && corrected_value === undefined)
    throw new Error("corrected record requires corrected_value");
  return {
    target: auditTarget(kind, id, field), kind, id, field, status,
    correction_kind: status === "corrected" ? correction_kind : null,
    root_cause: status === "corrected" ? root_cause : null,
    corrected_value: status === "corrected" ? corrected_value : null,
    note, audited_at: new Date().toISOString(),
  };
}

const ENUM = {
  "library:card_eligibility": CARD_ELIGIBILITY,
  "library:pass_pickup_default": PASS_PICKUP,
  "pass:coupon.form": COUPON_FORM,
  "pass:coupon.capacity.kind": CAPACITY_KIND,
  "pass:pass_form": PASS_FORM,
  "pass:residency_restriction.restricted": RESIDENCY_RESTRICTED,
  "pass:residency_restriction.scope": RESIDENCY_SCOPE,
  "attraction:visitor_eligibility.residency": VISITOR_RESIDENCY,
  "attraction:reservation.required": RESERVATION_REQUIRED,
};
const NUMBER = new Set(["pass:coupon.value","pass:coupon.capacity.n","attraction:price"]);

// Returns {control:"select"|"number"|"text", options?, value}
export function controlsFor(kind, field, currentValue) {
  const key = `${kind}:${field}`;
  if (ENUM[key]) return { control: "select", options: ENUM[key], value: currentValue ?? "" };
  if (NUMBER.has(key)) return { control: "number", value: currentValue ?? null };
  return { control: "text", value: currentValue ?? "" };
}

export const ASPECTS = ["coupon","pass_form","residency","reservation","attraction","other"];

// Feedback record — NOT machine-applied (build's apply_overrides only honors
// status "corrected"). Collected as JSON for later AI analysis.
export function buildFeedbackRecord({ kind, id, root_cause, aspects = [], feedback = "" }) {
  if (!ROOT_CAUSE.includes(root_cause))
    throw new Error("feedback record requires a valid root_cause");
  return {
    target: auditTarget(kind, id, "_feedback"),
    kind, id, field: "_feedback", status: "feedback",
    root_cause,
    aspects: (aspects || []).filter(a => ASPECTS.includes(a)),
    feedback: feedback || "",
    audited_at: new Date().toISOString(),
  };
}
