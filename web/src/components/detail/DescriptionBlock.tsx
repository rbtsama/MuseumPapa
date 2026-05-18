import { useState } from 'react';

interface Props {
  description: string | null;
}

const FOLD_THRESHOLD = 200;
const PREVIEW_CHARS = 150;

export function DescriptionBlock({ description }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (!description) return null;
  const needsFold = description.length > FOLD_THRESHOLD;
  const shown = !needsFold || expanded
    ? description
    : description.slice(0, PREVIEW_CHARS).trimEnd() + '…';

  return (
    <section style={{ padding: 14, borderBottom: '1px solid var(--rule)' }}>
      <h3 style={{
        margin: '0 0 8px',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--ink-3)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}>About</h3>
      <div style={{ fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.55 }}>
        {shown}
        {needsFold && !expanded && (
          <>
            {' '}
            <button
              type="button"
              onClick={() => setExpanded(true)}
              style={{
                background: 'transparent', border: 'none', padding: 0,
                color: 'var(--g)', fontWeight: 500, cursor: 'pointer', fontSize: 13,
              }}
            >Read more →</button>
          </>
        )}
      </div>
    </section>
  );
}
