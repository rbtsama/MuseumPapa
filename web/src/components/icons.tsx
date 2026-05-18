/**
 * Centralized inline-SVG icon set.
 *
 * All icons share one visual language:
 *   - stroke-only (fill="none"), currentColor, strokeWidth 2 (or 1.8 for Heart)
 *   - strokeLinecap="round", strokeLinejoin="round"
 *   - default 24×24 viewBox
 *
 * Props: size?: number, className?: string, style?: React.CSSProperties.
 * All strokes use currentColor — set color via parent or className/style.
 */

/* ── Shared base SVG props ───────────────────────────────────────────────── */

const BASE = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

interface IconProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

/* ── Location / time / ticket / warning icons (12 px default) ───────────── */

export function PinIcon({ size = 12, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
      <circle cx="12" cy="10" r="3"/>
    </svg>
  );
}

export function ClockIcon({ size = 12, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <circle cx="12" cy="12" r="10"/>
      <polyline points="12 6 12 12 16 14"/>
    </svg>
  );
}

export function TicketIcon({ size = 12, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <path d="M3 7a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3a2 2 0 0 0 0 4v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3a2 2 0 0 0 0-4z"/>
      <line x1="13" y1="7" x2="13" y2="10"/>
      <line x1="13" y1="14" x2="13" y2="17"/>
    </svg>
  );
}

export function TriangleExclamationIcon({ size = 12, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/>
      <line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  );
}

export function InfoIcon({ size = 12, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  );
}

export function CalendarIcon({ size = 13, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  );
}

export function LockIcon({ size = 13, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  );
}

/* ── Navigation chevrons ─────────────────────────────────────────────────── */

export function ChevronLeftIcon({ size = 18, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} strokeWidth={2.2} aria-hidden className={className} style={style}>
      <polyline points="15 18 9 12 15 6"/>
    </svg>
  );
}

export function ChevronDownIcon({ size = 14, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  );
}

export function ChevronUpIcon({ size = 14, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <polyline points="18 15 12 9 6 15"/>
    </svg>
  );
}

/* ── Search / check icons ────────────────────────────────────────────────── */

export function SearchIcon({ size = 14, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} aria-hidden className={className} style={style}>
      <circle cx="11" cy="11" r="7"/>
      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  );
}

export function CheckIcon({ size = 11, className, style }: IconProps) {
  return (
    <svg {...BASE} width={size} height={size} strokeWidth={3} aria-hidden className={className} style={style}>
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  );
}

/* ── Heart icon (fill-toggle) ────────────────────────────────────────────── */

interface HeartIconProps {
  filled: boolean;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function HeartIcon({ filled, size = 18, className, style }: HeartIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ display: 'block', ...style }}
      className={className}
    >
      <path d="M12 21s-7-4.5-9.4-9C.7 7.7 3.4 4 7.4 4c1.7 0 3.3.8 4.6 2.1C13.3 4.8 14.9 4 16.6 4c4 0 6.7 3.7 4.8 8-2.4 4.5-9.4 9-9.4 9z"/>
    </svg>
  );
}
