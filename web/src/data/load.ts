import librariesJson from '../../../data/structured/libraries.json';
import attractionsJson from '../../../data/structured/attractions.json';
import passesJson from '../../../data/structured/passes.json';
import branchesJson from '../../../data/structured/branches.json';
import type { LibrariesJson, AttractionsJson, PassesJson, BranchesJson, Library, Attraction, Pass, Branch } from './types';

const libraries = (librariesJson as unknown as LibrariesJson).libraries;
const attractions = (attractionsJson as unknown as AttractionsJson).attractions;
const passes = (passesJson as unknown as PassesJson).passes;
const branches = (branchesJson as unknown as BranchesJson).branches;

const libById = new Map(libraries.map(l => [l.id, l]));
const attrBySlug = new Map(attractions.map(a => [a.slug, a]));
const passesByAttr = new Map<string, Pass[]>();
for (const p of passes) {
  const arr = passesByAttr.get(p.attraction_slug) ?? [];
  arr.push(p); passesByAttr.set(p.attraction_slug, arr);
}
const branchesByLib = new Map<string, Branch[]>();
for (const b of branches) {
  const arr = branchesByLib.get(b.library_id) ?? [];
  arr.push(b); branchesByLib.set(b.library_id, arr);
}

export const getLibraries = (): Library[] => libraries;
export const getLibrary = (id: string): Library | undefined => libById.get(id);
export const getAttractions = (): Attraction[] => attractions;
export const getAttractionBySlug = (slug: string): Attraction | undefined => attrBySlug.get(slug);
export const getPasses = (): Pass[] => passes;
export const getPassesForAttraction = (slug: string): Pass[] => passesByAttr.get(slug) ?? [];
export const getBranchesForLibrary = (id: string): Branch[] => branchesByLib.get(id) ?? [];
