// Vercel Edge function — on-demand Assabet availability proxy.
//
// WHY: passes.json ships a static snapshot of each Assabet pass's calendar
// (taken at build time). That snapshot goes stale within hours as patrons
// book and release slots. For the 52 Assabet libraries we can fetch a
// fresh calendar at click-time — no auth, no card, just the public
// by-museum/<slug>/<year-month>/ page. The other two platforms (libcal /
// museumkey) need a logged-in barcode for availability, so they keep
// using the build-time snapshot + a "not real-time" banner in the UI.
//
// USAGE: GET /api/availability?url=<assabet-by-museum-url>&month=YYYY-MM
//   The library-supplied page URL is taken from passes.json — the function
//   refuses anything not on assabetinteractive.com.
//
// SAFETY: read-only proxy. Strips the request before forwarding (no
// cookies, no auth headers from the caller). Output JSON only; the
// fetched HTML is parsed server-side and discarded.

export const config = { runtime: "edge" };

const ALLOW_HOST = "assabetinteractive.com";
const MONTH_NAMES = ["january","february","march","april","may","june",
                     "july","august","september","october","november","december"];

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36";

// Mirrors the cell regex in src/malibbene/sources_v2/assabet/availability.py.
const CELL_RE =
  /class="(day\s+day-(?:mon|tue|wed|thu|fri|sat|sun)\s+day-(\d{4}-\d{2}-\d{2})[^"]*)"/gi;

type DayStatus = "available" | "booked" | "closed" | "unavailable";

function classify(cls: string): DayStatus | null {
  const tokens = new Set(cls.split(/\s+/));
  if (tokens.has("day-blank")) return null;
  if (tokens.has("day-has-openings")) return "available";
  if (tokens.has("day-past")) return "closed";
  if (tokens.has("day-unavailable")) return "unavailable";
  if (tokens.has("day-no-openings")) return "booked";
  return "unavailable";
}

function parseCalendar(html: string): Record<string, DayStatus> {
  const out: Record<string, DayStatus> = {};
  for (const m of html.matchAll(CELL_RE)) {
    const status = classify(m[1]);
    if (!status) continue;
    const date = m[2];
    if (out[date]) continue;
    out[date] = status;
  }
  return out;
}

function monthUrl(passUrl: string, month: string): string {
  // pass URL ends in /by-museum/<slug>/  → add /<year>-<monthname>/ for
  // forward months. The bare URL already shows the current month.
  const [y, mo] = month.split("-").map(Number);
  if (!y || !mo) return passUrl;
  const today = new Date();
  const isCurrent = y === today.getFullYear() && mo === today.getMonth() + 1;
  if (isCurrent) return passUrl;
  const base = passUrl.replace(/\/$/, "");
  return `${base}/${y}-${MONTH_NAMES[mo - 1]}/`;
}

export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const target = url.searchParams.get("url");
  const month = url.searchParams.get("month") || "";

  if (!target) {
    return json({ error: "missing ?url=" }, 400);
  }
  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return json({ error: "url is not valid" }, 400);
  }
  if (!parsed.hostname.endsWith(ALLOW_HOST)) {
    return json({ error: `only ${ALLOW_HOST} allowed` }, 403);
  }
  if (month && !/^\d{4}-\d{2}$/.test(month)) {
    return json({ error: "month must be YYYY-MM" }, 400);
  }

  const fetchUrl = month ? monthUrl(target, month) : target;
  try {
    const r = await fetch(fetchUrl, {
      headers: { "User-Agent": UA, "Accept": "text/html,*/*" },
      redirect: "follow",
    });
    if (!r.ok) {
      return json({
        error: `upstream ${r.status}`,
        upstream_url: fetchUrl,
      }, 502);
    }
    const html = await r.text();
    const days = parseCalendar(html);
    return json({
      source: fetchUrl,
      month: month || null,
      days,
      fetched_at: new Date().toISOString(),
    }, 200, {
      // Edge cache for 15 min, stale-while-revalidate for an hour. A
      // booking-grid status changing within 15 min is rare, and the SWR
      // window keeps clicks instant during a spike.
      "Cache-Control": "s-maxage=900, stale-while-revalidate=3600",
    });
  } catch (e) {
    return json({ error: `fetch failed: ${(e as Error).message}` }, 502);
  }
}

function json(body: unknown, status = 200, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      ...extra,
    },
  });
}
