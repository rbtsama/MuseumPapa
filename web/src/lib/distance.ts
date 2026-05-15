import type { Geo } from '../data/types';

const R_MILES = 3958.8;

export function haversineMiles(a: Geo, b: Geo): number {
  const phi1 = (a.lat * Math.PI) / 180;
  const phi2 = (b.lat * Math.PI) / 180;
  const dphi = ((b.lat - a.lat) * Math.PI) / 180;
  const dlam = ((b.lon - a.lon) * Math.PI) / 180;
  const x =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
  return 2 * R_MILES * Math.asin(Math.sqrt(x));
}

/**
 * Lookup a MA ZIP code → centroid using Nominatim, with localStorage cache.
 * Returns null if ZIP can't be geocoded or input is invalid.
 *
 * Note: browser CORS allows Nominatim queries. We rate-limit to 1 req/sec
 * client-side (Nominatim policy). Cached in localStorage so repeat lookups
 * are free.
 */
const ZIP_CACHE_KEY = 'museumpass-ma.zip-centroids';

interface ZipCache { [zip: string]: { lat: number; lon: number } | null }

function loadZipCache(): ZipCache {
  try {
    const raw = localStorage.getItem(ZIP_CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveZipCache(cache: ZipCache): void {
  try {
    localStorage.setItem(ZIP_CACHE_KEY, JSON.stringify(cache));
  } catch { /* swallow */ }
}

let lastNominatimAt = 0;

async function rateLimit(): Promise<void> {
  const elapsed = Date.now() - lastNominatimAt;
  if (elapsed < 1100) {
    await new Promise((r) => setTimeout(r, 1100 - elapsed));
  }
  lastNominatimAt = Date.now();
}

export async function geocodeZip(zip: string): Promise<Geo | null> {
  if (!/^\d{5}$/.test(zip)) return null;
  const cache = loadZipCache();
  if (zip in cache) return cache[zip];

  await rateLimit();
  try {
    const url = `https://nominatim.openstreetmap.org/search?postalcode=${zip}&country=US&format=json&limit=1`;
    const resp = await fetch(url, {
      headers: { 'Accept': 'application/json' },
    });
    if (!resp.ok) return null;
    const arr = await resp.json();
    if (!Array.isArray(arr) || arr.length === 0) {
      cache[zip] = null;
      saveZipCache(cache);
      return null;
    }
    const entry: Geo = { lat: parseFloat(arr[0].lat), lon: parseFloat(arr[0].lon) };
    cache[zip] = entry;
    saveZipCache(cache);
    return entry;
  } catch {
    return null;  // network error — DON'T cache (per plan-1 geocode design)
  }
}
