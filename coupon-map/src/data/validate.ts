// Runtime mirror of scripts/verify-data.mjs. Runs at app load. Throws on any
// fidelity violation so an inconsistent state can never get to the UI.
import type { Attraction, Library, Pass } from "./types";

const PASS_FORM = new Set(["digital_email", "physical_coupon", "physical_circ"]);
const VERDICT = new Set(["network_open", "own_card_only", "not_verified", "ambiguous"]);
const RESIDENCY = new Set(["no", "yes", "unknown"]);
const ELIGIBILITY = new Set(["ma_resident", "town_resident", "town_or_works", "network", "unknown"]);

export function validate(libs: Library[], attrs: Attraction[], passes: Pass[]) {
  const libIds = new Set(libs.map((l) => l.id));
  const attrSlugs = new Set(attrs.map((a) => a.slug));
  const errs: string[] = [];

  for (const p of passes) {
    if (!attrSlugs.has(p.attraction_slug))
      errs.push(`orphan attraction_slug: ${p.attraction_slug} (lib=${p.library_id})`);
    if (!libIds.has(p.library_id))
      errs.push(`orphan library_id: ${p.library_id} (attr=${p.attraction_slug})`);
    if (!PASS_FORM.has(p.pass_form))
      errs.push(`unknown pass_form: ${p.pass_form} (${p.library_id}/${p.attraction_slug})`);
    const v = p.booking_access_probe?.verdict;
    if (v && !VERDICT.has(v)) errs.push(`unknown verdict: ${v}`);
    const r = p.residency_restriction?.restricted;
    if (r && !RESIDENCY.has(r)) errs.push(`unknown residency: ${r}`);
    if (!p.coupon?.summary)
      errs.push(`missing coupon.summary: ${p.library_id}/${p.attraction_slug}`);
  }
  for (const l of libs) {
    if (!ELIGIBILITY.has(l.card_eligibility))
      errs.push(`unknown card_eligibility: ${l.card_eligibility} (${l.id})`);
  }

  if (errs.length) {
    // Loud, fatal — UI never paints an inconsistent state.
    throw new Error(`Data fidelity violation (${errs.length}):\n` + errs.slice(0, 20).join("\n"));
  }
}
