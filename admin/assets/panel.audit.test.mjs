import { test } from "node:test";
import assert from "node:assert/strict";
import { auditTarget, buildRecord, controlsFor, buildFeedbackRecord, ASPECTS, CARD_ELIGIBILITY, COUPON_FORM } from "./panel.audit.mjs";

test("auditTarget composes kind:id:field", () => {
  assert.equal(auditTarget("library","wakefield","card_eligibility"), "library:wakefield:card_eligibility");
});
test("buildRecord: verified_ok needs no value/root_cause", () => {
  const r = buildRecord({kind:"pass", id:"acton__mfa", field:"_verdict", status:"verified_ok"});
  assert.equal(r.target, "pass:acton__mfa:_verdict");
  assert.equal(r.status, "verified_ok");
  assert.equal(r.corrected_value, null);
  assert.equal(r.correction_kind, null);
  assert.ok(r.audited_at);
});
test("buildRecord: corrected carries value + correction_kind + root_cause", () => {
  const r = buildRecord({kind:"library", id:"wakefield", field:"card_eligibility",
    status:"corrected", correction_kind:"value_wrong", root_cause:"extraction_error",
    corrected_value:"ma_resident", note:"checked site"});
  assert.equal(r.corrected_value, "ma_resident");
  assert.equal(r.correction_kind, "value_wrong");
  assert.equal(r.root_cause, "extraction_error");
  assert.equal(r.note, "checked site");
});
test("buildRecord: corrected requires a defined value", () => {
  assert.throws(() => buildRecord({kind:"library",id:"x",field:"card_eligibility",status:"corrected"}));
});
test("controlsFor: enum field -> select with options", () => {
  const c = controlsFor("library","card_eligibility","unknown");
  assert.equal(c.control, "select");
  assert.deepEqual(c.options, CARD_ELIGIBILITY);
  assert.equal(c.value, "unknown");
});
test("controlsFor: coupon form -> select; value -> number", () => {
  assert.equal(controlsFor("pass","coupon.form","free").control, "select");
  assert.equal(controlsFor("pass","coupon.value",50).control, "number");
});
test("controlsFor: unknown field -> text", () => {
  assert.equal(controlsFor("attraction","note","").control, "text");
});

test("buildFeedbackRecord: builds a feedback-status record with cell target", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"acton__ecotarium",
    root_cause:"extraction_error", aspects:["coupon","pass_form"], feedback:"成人是买一送一" });
  assert.equal(r.target, "pass:acton__ecotarium:_feedback");
  assert.equal(r.status, "feedback");
  assert.equal(r.field, "_feedback");
  assert.equal(r.root_cause, "extraction_error");
  assert.deepEqual(r.aspects, ["coupon","pass_form"]);
  assert.equal(r.feedback, "成人是买一送一");
  assert.ok(r.audited_at);
});

test("buildFeedbackRecord: drops unknown aspects, defaults empty", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"unobtainable" });
  assert.deepEqual(r.aspects, []);
  assert.equal(r.feedback, "");
});

test("buildFeedbackRecord: rejects invalid root_cause", () => {
  assert.throws(() => buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"nope" }));
});

test("buildFeedbackRecord: filters junk aspects against ASPECTS", () => {
  const r = buildFeedbackRecord({ kind:"pass", id:"x__y", root_cause:"unobtainable",
    aspects:["coupon","garbage","other"] });
  assert.deepEqual(r.aspects, ["coupon","other"]);
  assert.ok(ASPECTS.includes("reservation"));
});
