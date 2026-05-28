// Copy data/structured/{libraries,attractions,passes,branches}.json -> public/data/
// Produce manifest.json with sha256 + row count + mtime so the app can detect
// any drift. Runs automatically before `dev` and `build`.
import { createHash } from "node:crypto";
import { mkdir, copyFile, readFile, writeFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const srcDir = resolve(repo, "data", "structured");
const dstDir = resolve(here, "..", "public", "data");

const files = ["libraries.json", "attractions.json", "passes.json", "branches.json"];

function rowsOf(parsed) {
  // each structured file is { _meta, <entityKey>: [...] }
  if (Array.isArray(parsed)) return parsed.length;
  for (const k of Object.keys(parsed)) {
    if (Array.isArray(parsed[k])) return parsed[k].length;
  }
  return null;
}

await mkdir(dstDir, { recursive: true });
const manifest = { generated_at: new Date().toISOString(), files: {} };

for (const name of files) {
  const src = resolve(srcDir, name);
  const dst = resolve(dstDir, name);
  await copyFile(src, dst);
  const buf = await readFile(src);
  const sha = createHash("sha256").update(buf).digest("hex").slice(0, 16);
  const parsed = JSON.parse(buf.toString("utf8"));
  const st = await stat(src);
  manifest.files[name] = {
    bytes: buf.length,
    sha256_16: sha,
    rows: rowsOf(parsed),
    src_mtime: st.mtime.toISOString(),
  };
  console.log(`  synced ${name}  ${buf.length}B  sha=${sha}  rows=${manifest.files[name].rows}`);
}

await writeFile(resolve(dstDir, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log("sync-data ok");
