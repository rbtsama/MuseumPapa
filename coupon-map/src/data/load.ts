import type { Attraction, Branch, DataBundle, Library, Pass } from "./types";
import { validate } from "./validate";

// Network display order — most-to-least libraries, matches the data shape.
const NETWORK_ORDER = ["Minuteman", "NOBLE", "MVLC", "OCLN", "MBLN", "BPL"];

async function getJSON<T>(path: string): Promise<T> {
  // no-store so a stale browser copy can never make correct data look wrong.
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`fetch ${path} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export async function loadAll(): Promise<DataBundle> {
  const [libsDoc, attrsDoc, passesDoc, branchesDoc] = await Promise.all([
    getJSON<{ libraries: Library[] }>("/data/libraries.json"),
    getJSON<{ attractions: Attraction[] }>("/data/attractions.json"),
    getJSON<{ passes: Pass[] }>("/data/passes.json"),
    getJSON<{ branches: Branch[] }>("/data/branches.json"),
  ]);

  const libraries = libsDoc.libraries;
  const attractions = attrsDoc.attractions;
  const passes = passesDoc.passes;
  const branches = branchesDoc.branches;

  // Fidelity gate — throws if anything is off; better a red screen than a wrong cell.
  validate(libraries, attractions, passes);

  const libById = new Map(libraries.map((l) => [l.id, l]));
  const attrBySlug = new Map(attractions.map((a) => [a.slug, a]));
  // Join key is pinned to attraction_slug (NOT attraction_rawslug — see verify-data).
  const passByPair = new Map<string, Pass>();
  for (const p of passes) passByPair.set(`${p.attraction_slug}::${p.library_id}`, p);

  // Cell-count contract: matrix paints one cell per joined pass.
  if (passByPair.size !== passes.length) {
    throw new Error(`duplicate (attraction,library) pair detected: ${passes.length} passes, ${passByPair.size} pairs`);
  }

  const byNet = new Map<string, Library[]>();
  for (const l of libraries) {
    if (!byNet.has(l.network)) byNet.set(l.network, []);
    byNet.get(l.network)!.push(l);
  }
  for (const arr of byNet.values()) arr.sort((a, b) => a.town.localeCompare(b.town));
  const networks: DataBundle["networks"] = [];
  for (const n of NETWORK_ORDER) if (byNet.has(n)) networks.push({ network: n, libraries: byNet.get(n)! });
  for (const [n, arr] of byNet) if (!NETWORK_ORDER.includes(n)) networks.push({ network: n, libraries: arr });

  return { libraries, attractions, passes, branches, passByPair, libById, attrBySlug, networks };
}
