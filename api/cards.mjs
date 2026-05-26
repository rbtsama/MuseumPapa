// Vercel serverless: expose library card numbers from environment variables.
// GET /api/cards -> { library_id: barcode, ... }
//
// Card numbers (barcodes) are SENSITIVE. They live ONLY as Vercel env vars
// (<LIB>_BARCODE, e.g. WAKEFIELD_BARCODE) — never committed, mirroring the
// local .env. Set them in the Vercel project settings.
//
// ⚠ SECURITY: this endpoint returns the barcodes to whoever can reach it. The
// admin deployment MUST be access-protected (Vercel password / SSO / auth gate)
// or these values are public. If the admin app is not protected online, do NOT
// configure the *_BARCODE env vars on Vercel — keep card numbers local-only.
export default function handler(req, res) {
  if (req.method !== "GET") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }
  const cards = {};
  for (const [k, v] of Object.entries(process.env)) {
    if (k.endsWith("_BARCODE") && v) {
      cards[k.slice(0, -"_BARCODE".length).toLowerCase()] = v;
    }
  }
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json(cards);
}
