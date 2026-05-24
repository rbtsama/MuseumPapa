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
  // Email passes dedup to the single best one. We only FORCE an email pass to the
  // top when it's eligible (so a convenient email pass leads); an ineligible email
  // pass must NOT be surfaced above eligible passes — let it fall into normal
  // score-sorted order instead.
  const out: RecommendedPass[] = [];
  const emails = scored.filter(r => r.pass.pass_form === 'digital_email');
  const eligibleEmail = emails.find(r => r.verdict.eligible);
  if (eligibleEmail) out.push(eligibleEmail);
  // The one email pass we keep (eligible if any, else best-scored email).
  const keptEmail = eligibleEmail ?? emails[0] ?? null;
  for (const r of scored) {
    if (out.length >= 4) break;
    if (r.pass.pass_form === 'digital_email') {
      // Skip all email passes except the single kept one (and only if not already pushed).
      if (r === eligibleEmail) continue;     // already at out[0]
      if (r !== keptEmail) continue;          // dedup: drop the rest
    }
    out.push(r);
  }
  return out.slice(0, 4);
}
