import { useMemo, useState } from 'react';
import type { Geo } from '../data/types';
import { getBranchesForLibrary } from '../data/load';
import { haversineMiles } from '../lib/distance';

interface PickupBranchesProps {
  libraryId: string;
  /** User home centroid (from their ZIP). null = unknown → no distances. */
  userGeo: Geo | null;
}

/**
 * For a physical-pickup pass at a multi-branch library (BPL, Brookline,
 * Cambridge), the pass / availability / policy are the SAME at every branch —
 * the branch is only *where you collect it*. So we show one collapsible line,
 * not N duplicated rows: "🏛 N branches · nearest X (1.2 mi)", expandable into
 * a distance-sorted list. Renders nothing for single-branch libraries (the
 * common case) — the location is already shown on the row.
 */
export function PickupBranches({ libraryId, userGeo }: PickupBranchesProps) {
  const [open, setOpen] = useState(false);

  const ranked = useMemo(() => {
    const branches = getBranchesForLibrary(libraryId);
    return branches
      .map(b => ({
        name: b.name,
        distanceMi: userGeo && b.geo ? haversineMiles(userGeo, b.geo) : null,
      }))
      // Branches we can place go first (nearest → farthest); unplaceable ones
      // fall to the bottom, ordered by name so the list is still stable.
      .sort((a, b) => {
        if (a.distanceMi != null && b.distanceMi != null) return a.distanceMi - b.distanceMi;
        if (a.distanceMi != null) return -1;
        if (b.distanceMi != null) return 1;
        return a.name.localeCompare(b.name);
      });
  }, [libraryId, userGeo]);

  if (ranked.length <= 1) return null;

  const nearest = ranked[0];
  const summary = nearest.distanceMi != null
    ? `${ranked.length} branches · nearest ${nearest.name} (${nearest.distanceMi.toFixed(1)} mi)`
    : `Pick up at any of ${ranked.length} branches`;

  return (
    <div style={{ marginTop: 4 }}>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(o => !o); }}
        aria-expanded={open}
        style={{
          background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 11, color: 'var(--ink-3)', fontWeight: 500,
        }}
      >
        <span aria-hidden>🏛</span>
        <span>{summary}</span>
        <span aria-hidden style={{ color: 'var(--g)' }}>{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <ul style={{ listStyle: 'none', margin: '4px 0 0', padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {ranked.map(b => (
            <li key={b.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11, color: 'var(--ink-2)' }}>
              <span>{b.name}</span>
              {b.distanceMi != null && (
                <span style={{ color: 'var(--ink-3)', flexShrink: 0 }}>{b.distanceMi.toFixed(1)} mi</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
