import librariesJson from '../../../data/structured/libraries.json';
import attractionsJson from '../../../data/structured/attractions.json';
import passesJson from '../../../data/structured/passes.json';
import branchesJson from '../../../data/structured/branches.json';
import type {
  LibrariesJson, AttractionsJson, PassesJson, BranchesJson,
  Library, Attraction, Pass, Branch,
} from './types';

const _libraries = librariesJson as LibrariesJson;
const _attractions = attractionsJson as AttractionsJson;
const _passes = passesJson as PassesJson;
const _branches = branchesJson as BranchesJson;
const _branchById: Map<string, Branch> = new Map(_branches.branches.map(b => [b.id, b]));

export function getLibraries(): Library[] {
  return _libraries.libraries;
}

export function getAttractions(): Attraction[] {
  return _attractions.attractions;
}

export function getAttractionBySlug(slug: string): Attraction | undefined {
  return _attractions.attractions.find(a => a.slug === slug);
}

export function getPasses(): Pass[] {
  return _passes.passes;
}

export function getPassesForAttraction(slug: string): Pass[] {
  return _passes.passes.filter(p => p.attraction_slug === slug);
}

export function getBranchesForPass(p: Pass): Branch[] {
  return p.pickup_branches.map(id => _branchById.get(id)).filter((b): b is Branch => !!b);
}
