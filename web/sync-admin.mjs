// Sync admin panel + structured JSON into web/public/ so Vite (and Vercel)
// serve them as static assets at /admin/* and /data/structured/*.
// Runs via `pnpm run copy:admin` or automatically as a prebuild hook.

import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve("..");
const PUB = "public";

function syncDir(src, dst) {
  if (fs.existsSync(dst)) fs.rmSync(dst, { recursive: true, force: true });
  if (!fs.existsSync(src)) {
    console.warn(`[sync-admin] missing source: ${src}`);
    return;
  }
  fs.cpSync(src, dst, { recursive: true });
  console.log(`[sync-admin] ${src} -> ${dst}`);
}

// 1. admin/ -> public/admin/
syncDir(path.join(ROOT, "admin"), path.join(PUB, "admin"));

// 2. data/structured/{libraries,attractions,branches,passes}.json -> public/data/structured/
const structDst = path.join(PUB, "data", "structured");
fs.mkdirSync(structDst, { recursive: true });
for (const f of ["libraries", "attractions", "branches", "passes"]) {
  const s = path.join(ROOT, "data", "structured", `${f}.json`);
  const d = path.join(structDst, `${f}.json`);
  fs.copyFileSync(s, d);
}
console.log(`[sync-admin] 4 structured JSON files -> ${structDst}`);
