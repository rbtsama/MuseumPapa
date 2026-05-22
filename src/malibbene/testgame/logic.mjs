// 纯决策逻辑：无 DOM 依赖。构建时会被剥掉 `export` 内联进 HTML。
export function classifyAttraction(attractionSlug, data, heldLibIds, homeTown) {
  const held = new Set(heldLibIds);
  const enriched = data.passes
    .filter((p) => p.attraction_slug === attractionSlug)
    .map((p) => ({
      ...p,
      held: held.has(p.library_id),
      residentOK: p.residency !== 'yes' || homeTown === p.library_town,
    }));

  const fullyUsable = enriched.filter((p) => p.held && p.residentOK);
  const heldPasses = enriched.filter((p) => p.held);
  const residentOKPasses = enriched.filter((p) => p.residentOK);

  let state;
  let tags;
  if (fullyUsable.length > 0) { state = 1; tags = []; }
  else if (heldPasses.length > 0) { state = 3; tags = ['resident_only']; }
  else if (residentOKPasses.length > 0) { state = 2; tags = ['library_pass_needed']; }
  else { state = 4; tags = ['resident_only', 'library_pass_needed']; }

  const uniqLibs = (arr) => {
    const seen = new Set();
    const out = [];
    for (const p of arr) {
      if (seen.has(p.library_id)) continue;
      seen.add(p.library_id);
      out.push({ library_id: p.library_id, library_name: p.library_name, network: p.network, library_town: p.library_town });
    }
    return out;
  };

  return {
    state,
    tags,
    passes: enriched,
    usableCards: uniqLibs(state === 1 ? fullyUsable : heldPasses),
    recommendCards: uniqLibs(residentOKPasses),
    offeringCards: uniqLibs(enriched),
    residentOnlyTowns: [...new Set(heldPasses.filter((p) => p.residency === 'yes').map((p) => p.library_town))],
  };
}
