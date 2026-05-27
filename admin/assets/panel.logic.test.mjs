import { test } from "node:test";
import assert from "node:assert/strict";
import { cardOk, residencyOk, cellTier, availStatus, rowSortKey, bestPolicy, headlinePolicy, shortSummary } from "./panel.logic.mjs";

const libsById = {
  wakefield: { id: "wakefield", network: "NOBLE", town: "Wakefield", resident_zips: ["01880"] },
  reading:   { id: "reading",   network: "NOBLE", town: "Reading",  resident_zips: ["01867"] },
  bpl:       { id: "bpl",       network: "BPL",   town: "Boston",   resident_zips: ["02118"] },
};
const maZips = new Set(["01880", "01867", "02118"]);

test("cardOk: own id matches", () => {
  assert.equal(cardOk(libsById.wakefield, ["wakefield"], libsById), true);
});
test("cardOk: same network matches", () => {
  assert.equal(cardOk(libsById.reading, ["wakefield"], libsById), true);
});
test("cardOk: different network fails", () => {
  assert.equal(cardOk(libsById.bpl, ["wakefield"], libsById), false);
});
test("cardOk: requiresOwnCard blocks same-network sibling card", () => {
  // reading pass needs its OWN card — a wakefield (same NOBLE) card is rejected
  assert.equal(cardOk(libsById.reading, ["wakefield"], libsById, true), false);
});
test("cardOk: requiresOwnCard still allows the library's own card", () => {
  assert.equal(cardOk(libsById.reading, ["reading"], libsById, true), true);
});
test("residencyOk: no restriction passes", () => {
  const r = residencyOk({ residency_restriction: { restricted: "no" } }, libsById.wakefield, null, "99999", maZips);
  assert.equal(r.ok, true);
});
test("residencyOk: town scope rejects non-resident zip", () => {
  const pass = { residency_restriction: { restricted: "yes", scope: "town" } };
  const r = residencyOk(pass, libsById.wakefield, null, "01867", maZips);
  assert.equal(r.ok, false);
});
test("residencyOk: ma scope accepts MA zip", () => {
  const pass = { residency_restriction: { restricted: "yes", scope: "ma" } };
  assert.equal(residencyOk(pass, libsById.wakefield, null, "01867", maZips).ok, true);
});
test("residencyOk: ma scope accepts a real MA zip outside seed towns (01886 Westford)", () => {
  // Regression: isMaZip used to key off the ~59 seed-town set, so a genuine MA
  // resident in Westford got a false "MA residents only" block.
  const pass = { residency_restriction: { restricted: "yes", scope: "ma" } };
  assert.equal(residencyOk(pass, libsById.wakefield, null, "01886", maZips).ok, true);
});
test("residencyOk: unknown passes with warn", () => {
  const r = residencyOk({ residency_restriction: { restricted: "unknown" } }, libsById.wakefield, null, "01880", maZips);
  assert.equal(r.ok, true);
  assert.equal(r.warn, true);
});
test("residencyOk: attraction ma_resident rejects non-MA", () => {
  const r = residencyOk({ residency_restriction: { restricted: "no" } }, libsById.wakefield,
    { visitor_eligibility: { residency: "ma_resident" } }, "99999", maZips);
  assert.equal(r.ok, false);
});
test("cellTier: a/b/c/d matrix", () => {
  assert.equal(cellTier(true, true), "a");
  assert.equal(cellTier(false, true), "b");
  assert.equal(cellTier(true, false), "c");
  assert.equal(cellTier(false, false), "d");
});
test("availStatus: maps states; no date -> none", () => {
  assert.equal(availStatus({ availability: { "2026-05-25": "available" } }, "2026-05-25"), "available");
  assert.equal(availStatus({ availability: { "2026-05-25": "booked" } }, "2026-05-25"), "booked");
  assert.equal(availStatus({ availability: {} }, "2026-05-25"), "unknown");
  assert.equal(availStatus({ availability: {} }, null), "none");
});
test("rowSortKey: best tier + available-first", () => {
  assert.deepEqual(rowSortKey([{ tier: "a", avail: "available" }]), [0, 0]);
  assert.deepEqual(rowSortKey([{ tier: "b", avail: "available" }, { tier: "c", avail: "available" }]), [1, 0]);
  assert.deepEqual(rowSortKey([{ tier: "a", avail: "booked" }]), [0, 1]);
  assert.deepEqual(rowSortKey([]), [9, 9]);
});
test("bestPolicy/shortSummary: pick strongest form, short glyphs", () => {
  const coupon = { audience_policies: [ { form: "dollar-off", value: 5 }, { form: "free" } ] };
  assert.equal(bestPolicy(coupon).form, "free");          // bestPolicy = pure strength
  assert.equal(shortSummary(coupon), "-$5");              // headline = the paid offer, not the free line
  assert.equal(shortSummary({ audience_policies: [{ form: "percent-off", value: 50 }] }), "-50%");
  assert.equal(shortSummary({ audience_policies: [{ form: "dollar-off", value: 10 }] }), "-$10");
  assert.equal(shortSummary({ audience_policies: [{ form: "per-person-price", value: 9 }] }), "$9");
  assert.equal(shortSummary({ audience_policies: [{ form: "discount" }] }), "disc");
  assert.equal(shortSummary(null), "?");
});

test("headlinePolicy: prefers adult/Everyone over a stronger kid offer", () => {
  const coupon = { audience_policies: [
    { audience: "Children under 3", form: "free" },
    { audience: "Adult", form: "percent-off", value: 50 },
  ] };
  assert.equal(headlinePolicy(coupon).audience, "Adult");
  assert.equal(shortSummary(coupon), "-50%");
});

test("headlinePolicy: prefers paid offer over a secondary free line when no adult audience", () => {
  // jfk-library shape: 'Single ticket 50% off' + 'Child free'. The matrix glyph
  // must not read FREE — mirrors the data-side summary_for fix (P0-2).
  const coupon = { audience_policies: [
    { audience: "Single ticket", form: "percent-off", value: 50 },
    { audience: "Child", form: "free" },
  ] };
  assert.equal(headlinePolicy(coupon).form, "percent-off");
  assert.equal(shortSummary(coupon), "-50%");
});

test("headlinePolicy: all-free stays FREE", () => {
  const coupon = { audience_policies: [
    { audience: "Adult", form: "free" }, { audience: "Child", form: "free" } ] };
  assert.equal(shortSummary(coupon), "FREE");
});

test("residencyOk: restricted=yes with unknown scope warns (not silently clean)", () => {
  // A4: matrix and detail paths disagreed here — matrix showed a clean tier-A.
  const r = residencyOk({ residency_restriction: { restricted: "yes", scope: null } },
    libsById.wakefield, null, "01880", maZips);
  assert.equal(r.ok, true);
  assert.equal(r.warn, true);
});
