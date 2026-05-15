import librariesJson from '../../../data/structured/libraries.json';
import attractionsJson from '../../../data/structured/attractions.json';
import passesJson from '../../../data/structured/passes.json';
import type { LibrariesJson, AttractionsJson, PassesJson, Library, Attraction, Pass } from './types';

const _libraries = librariesJson as LibrariesJson;
const _attractions = attractionsJson as AttractionsJson;
const _passes = passesJson as PassesJson;

export function getLibraries(): Library[] {
  return _libraries.libraries;
}

export function getLibraryById(id: string): Library | undefined {
  return _libraries.libraries.find(l => l.id === id);
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

export function getPassesForLibrary(libId: string): Pass[] {
  return _passes.passes.filter(p => p.library_id === libId);
}
