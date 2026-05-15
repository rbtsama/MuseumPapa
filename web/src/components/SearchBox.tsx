interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

/**
 * Compact pill-style search input. Same visual weight as DatePicker /
 * SortDropdown so the filter bar stays one consistent horizontal row.
 *
 * Filtering itself happens in the parent page (case-insensitive token
 * substring match across museum_name, town, and categories). This component
 * is presentational + value-controlled.
 */
export function SearchBox({ value, onChange, placeholder = 'Search attractions' }: Props) {
  return (
    <div
      className="relative inline-flex items-center rounded-md"
      style={{
        border: '1px solid var(--rule)',
        background: 'var(--white)',
        padding: '0 8px 0 28px',
        height: 32,
        minWidth: 180,
      }}
    >
      <span
        aria-hidden
        style={{
          position: 'absolute',
          left: 9,
          top: '50%',
          transform: 'translateY(-50%)',
          fontSize: 12,
          color: 'var(--ink-3)',
          pointerEvents: 'none',
        }}
      >
        🔍
      </span>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Search attractions"
        style={{
          background: 'transparent',
          border: 'none',
          outline: 'none',
          fontSize: 13,
          color: 'var(--ink-2)',
          width: '100%',
          padding: 0,
        }}
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          style={{
            position: 'absolute',
            right: 4,
            top: '50%',
            transform: 'translateY(-50%)',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--ink-3)',
            fontSize: 14,
            lineHeight: 1,
            padding: 4,
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}
