// End-to-end fidelity asserts. Fails the build if anything that would silently
// distort the matrix is detected. Mirrors src/data/validate.ts so dev catches
// the same problems whether tripped at build time or at app load time.
import { readFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(here, "..", "public", "data");

const PASS_FORM = new Set(["digital_email", "physical_coupon", "physical_circ"]);
const VERDICT = new Set(["network_open", "own_card_only", "not_verified", "ambiguous"]);
const RESIDENCY = new Set(["no", "yes", "unknown"]);
const ELIGIBILITY = new Set([
  "ma_resident",
  "town_resident",
  "town_or_works",
  "network",
  "unknown",
]);

const load = async (n) => JSON.parse(await readFile(resolve(dataDir, n), "utf8"));

const libs = (await load("libraries.json")).libraries;
const attrs = (await load("attractions.json")).attractions;
const passes = (await load("passes.json")).passes;

const libIds = new Set(libs.map((l) => l.id));
const attrSlugs = new Set(attrs.map((a) => a.slug));

const fail = (msg) => {
  console.error(`✗ ${msg}`);
  process.exitCode = 1;
};
const ok = (msg) => console.log(`✓ ${msg}`);

// JOIN integrity — the trap: 274 passes have attraction_slug != attraction_rawslug.
// We pin the join to attraction_slug; orphans must be 0.
const orphanA = passes.filter((p) => !attrSlugs.has(p.attraction_slug));
const orphanL = passes.filter((p) => !libIds.has(p.library_id));
orphanA.length === 0 ? ok(`pass.attraction_slug all join (n=${passes.length})`) : fail(`${orphanA.length} orphan attraction_slug`);
orphanL.length === 0 ? ok(`pass.library_id all join`) : fail(`${orphanL.length} orphan library_id`);

// Enum sanity — silent default on unknown enums was the historical silent-drop bug.
const badForm = passes.filter((p) => !PASS_FORM.has(p.pass_form));
const badVerdict = passes.filter((p) => !VERDICT.has(p.booking_access_probe?.verdict));
const badRes = passes.filter((p) => !RESIDENCY.has(p.residency_restriction?.restricted));
const badElig = libs.filter((l) => !ELIGIBILITY.has(l.card_eligibility));
badForm.length === 0 ? ok("pass_form ∈ known set") : fail(`${badForm.length} bad pass_form`);
badVerdict.length === 0 ? ok("booking_access.verdict ∈ known set") : fail(`${badVerdict.length} bad verdict`);
badRes.length === 0 ? ok("residency.restricted ∈ known set") : fail(`${badRes.length} bad residency`);
badElig.length === 0 ? ok("library.card_eligibility ∈ known set") : fail(`${badElig.length} bad eligibility`);

// Cell-count contract — the matrix renders one cell per joined pass.
const cellsExpected = passes.length;
const cellsJoined = passes.length - orphanA.length - orphanL.length;
cellsExpected === cellsJoined ? ok(`cell count contract holds (${cellsJoined})`) : fail("cell count mismatch");

// Three-state contract spot check — coupon.summary should never be empty
// because the matrix cell renders it verbatim. If it is, we want it loud.
const noSummary = passes.filter((p) => !p.coupon?.summary);
noSummary.length === 0 ? ok("every pass has coupon.summary") : fail(`${noSummary.length} pass missing coupon.summary`);

if (process.exitCode) {
  console.error("\nverify-data FAILED — fix data or join key before building.");
  process.exit(1);
}
console.log("\nverify-data ok");
