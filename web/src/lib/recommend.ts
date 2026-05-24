import { getPassesForAttraction, getLibrary, getAttractionBySlug } from '../data/load';
import { resolvePass, type User, type PassVerdict } from './eligibility';
import { passStrength } from './couponSummary';
import type { Pass } from '../data/types';

export interface RecommendedPass { pass: Pass; verdict: PassVerdict; score: number; }

export function recommend(slug: string, user: User, date?: Date): RecommendedPass[] {
  const attr = getAttractionBySlug(slug); if (!attr) return [];
  const scored: RecommendedPass[] = [];
  for (const pass of getPassesForAttraction(slug)) {
    const lib = getLibrary(pass.library_id); if (!lib) continue;
    const verdict = resolvePass(pass, lib, attr, user, date);
    let score = passStrength(pass.coupon) * 10;
    if (!verdict.eligible) score -= 1000;            // ineligible sinks
    if (verdict.warnings.length) score -= 5;          // unknown to the back
    scored.push({ pass, verdict, score });
  }
  scored.sort((a, b) => b.score - a.score);
  // Email: dedup to best 1; Pickup/Return: up to 3.
  const out: RecommendedPass[] = [];
  const email = scored.find(r => r.pass.pass_form === 'digital_email');
  if (email) out.push(email);
  for (const r of scored) {
    if (out.length >= 4) break;
    if (r.pass.pass_form === 'digital_email') continue;
    out.push(r);
  }
  return out.slice(0, 4);
}
