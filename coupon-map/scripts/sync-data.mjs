// Copy data/structured/{libraries,attractions,passes,branches}.json -> public/data/
// Produce manifest.json with sha256 + row count + mtime so the app can detect
// any drift. Also reads data/overrides/{libraries,attractions}/<id>/*.json
// and injects each override's {source, evidence} as a _evidence field on the
// corresponding record — the build pipeline only carries the corrected_value,
// not the provenance, so we re-attach it here so popovers can render the
// "原文 + 来源" bottom section.
// Runs automatically before `dev` and `build`.
import { createHash } from "node:crypto";
import { mkdir, copyFile, readFile, readdir, stat, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const srcDir = resolve(repo, "data", "structured");
const overridesDir = resolve(repo, "data", "overrides");
const dstDir = resolve(here, "..", "public", "data");

const files = ["libraries.json", "attractions.json", "passes.json", "branches.json"];

function rowsOf(parsed) {
  if (Array.isArray(parsed)) return parsed.length;
  for (const k of Object.keys(parsed)) {
    if (Array.isArray(parsed[k])) return parsed[k].length;
  }
  return null;
}

async function safeListdir(p) {
  try {
    return await readdir(p);
  } catch {
    return [];
  }
}

async function loadOverridesByEntity(entityDir) {
  // returns Map<id, Record<field, {source, evidence}>>
  const root = resolve(overridesDir, entityDir);
  const ids = await safeListdir(root);
  const out = new Map();
  for (const id of ids) {
    const idDir = resolve(root, id);
    const st = await stat(idDir).catch(() => null);
    if (!st?.isDirectory()) continue;
    const fields = await safeListdir(idDir);
    const rec = {};
    for (const f of fields) {
      if (!f.endsWith(".json")) continue;
      const field = f.replace(/\.json$/, "");
      const buf = await readFile(resolve(idDir, f)).catch(() => null);
      if (!buf) continue;
      try {
        const o = JSON.parse(buf.toString("utf8"));
        if (o.source || o.evidence) {
          rec[field] = { source: o.source || null, evidence: o.evidence || null };
        }
      } catch {}
    }
    if (Object.keys(rec).length) out.set(id, rec);
  }
  return out;
}

await mkdir(dstDir, { recursive: true });
const manifest = { generated_at: new Date().toISOString(), files: {} };

const libsEv = await loadOverridesByEntity("libraries");
const attrsEv = await loadOverridesByEntity("attractions");

for (const name of files) {
  const src = resolve(srcDir, name);
  const dst = resolve(dstDir, name);
  const buf = await readFile(src);
  const parsed = JSON.parse(buf.toString("utf8"));
  const st = await stat(src);

  // Inject _evidence for libraries / attractions records. Merge (not clobber)
  // override-derived _evidence onto whatever the build pipeline already
  // injected (e.g. source_block evidence for hours / card_eligibility /
  // visitor_eligibility). Override entries win per-field.
  const mergeEvidence = (base, ov) => {
    // Per-field deep merge so a build-injected verbatim `block` survives even
    // when an override supplies only {source, evidence} for the same field.
    const out = { ...(base || {}) };
    for (const [field, val] of Object.entries(ov || {})) {
      out[field] = { ...(out[field] || {}), ...val };
    }
    return out;
  };
  if (name === "libraries.json" && Array.isArray(parsed.libraries)) {
    for (const lib of parsed.libraries) {
      const ev = libsEv.get(lib.id);
      if (ev) lib._evidence = mergeEvidence(lib._evidence, ev);
    }
  } else if (name === "attractions.json" && Array.isArray(parsed.attractions)) {
    for (const a of parsed.attractions) {
      const ev = attrsEv.get(a.slug);
      if (ev) a._evidence = mergeEvidence(a._evidence, ev);
    }
  }

  const serialized = JSON.stringify(parsed, null, 2);
  await writeFile(dst, serialized, "utf8");
  const sha = createHash("sha256").update(serialized).digest("hex").slice(0, 16);
  manifest.files[name] = {
    bytes: Buffer.byteLength(serialized, "utf8"),
    sha256_16: sha,
    rows: rowsOf(parsed),
    src_mtime: st.mtime.toISOString(),
  };
  console.log(
    `  synced ${name}  ${manifest.files[name].bytes}B  sha=${sha}  rows=${manifest.files[name].rows}` +
      (name === "libraries.json" ? `  +${libsEv.size} _evidence` : "") +
      (name === "attractions.json" ? `  +${attrsEv.size} _evidence` : "")
  );
}

await writeFile(resolve(dstDir, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log("sync-data ok");
