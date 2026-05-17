interface Props {
  active: boolean;
  count: number;
  onToggle: () => void;
}

export function FavoritesToggle({ active, count, onToggle }: Props) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      className="inline-flex items-center gap-1.5 rounded-md whitespace-nowrap"
      style={{
        background: active ? 'var(--rd-pale)' : 'transparent',
        border: `1px solid ${active ? 'var(--rd)' : 'var(--rule)'}`,
        padding: '6px 10px',
        fontSize: 12,
        color: active ? 'var(--rd)' : 'var(--ink-2)',
        cursor: 'pointer',
        fontWeight: 500,
      }}
    >
      <span aria-hidden style={{ fontSize: 13 }}>{active ? '♥' : '♡'}</span>
      <span>Favorites</span>
      <span style={{
        fontSize: 11,
        color: active ? 'var(--rd)' : 'var(--ink-3)',
        fontWeight: 400,
      }}>{count}</span>
    </button>
  );
}
