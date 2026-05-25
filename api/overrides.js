// Vercel serverless: shared audit store backed by a GitHub file.
// GET  /api/overrides            -> {target: record, ...}
// POST /api/overrides {record}   -> upsert one (must include "target")
// POST /api/overrides {"revoke": target} -> remove one
const FILE = "data/overrides/audit_overrides.json";

function ghHeaders() {
  return {
    Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "museumpapa-admin",
  };
}
function api(path) {
  return `https://api.github.com/repos/${process.env.GITHUB_REPO}/contents/${path}`;
}

async function readFile() {
  const ref = process.env.GITHUB_BRANCH || "main";
  const res = await fetch(`${api(FILE)}?ref=${ref}`, { headers: ghHeaders() });
  if (res.status === 404) return { store: {}, sha: undefined };
  if (!res.ok) throw new Error(`github read ${res.status}`);
  const json = await res.json();
  const store = JSON.parse(Buffer.from(json.content, "base64").toString("utf-8"));
  return { store, sha: json.sha };
}

async function writeFile(store, sha) {
  const body = {
    message: "admin: audit override update",
    content: Buffer.from(JSON.stringify(store, null, 2)).toString("base64"),
    branch: process.env.GITHUB_BRANCH || "main",
    ...(sha ? { sha } : {}),
  };
  const res = await fetch(api(FILE), {
    method: "PUT", headers: ghHeaders(), body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`github write ${res.status}`);
}

export default async function handler(req, res) {
  try {
    if (req.method === "GET") {
      const { store } = await readFile();
      return res.status(200).json(store);
    }
    if (req.method === "POST") {
      const payload = typeof req.body === "string" ? JSON.parse(req.body) : req.body || {};
      const { store, sha } = await readFile();
      if ("revoke" in payload) {
        delete store[payload.revoke];
      } else if (payload.target) {
        store[payload.target] = payload;
      } else {
        return res.status(400).json({ error: "record missing 'target'" });
      }
      await writeFile(store, sha);
      return res.status(200).json(store);
    }
    return res.status(405).json({ error: "method not allowed" });
  } catch (e) {
    return res.status(500).json({ error: String(e.message || e) });
  }
}
