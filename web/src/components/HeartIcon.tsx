interface Props {
  filled: boolean;
  size?: number;
}

/**
 * Heart icon used by FavoriteButton (card overlay + inline) and FavoritesToggle.
 *
 * Why a single SVG and not Unicode glyphs: ❤ U+2764 renders as a chunky
 * red emoji while ♡ U+2661 renders as a thin text outline, so the same
 * "font-size" produces two visibly different sizes — exactly the unstable
 * pre-click / post-click sizing the user reported. One path with a fill
 * toggle keeps the geometry identical between states.
 */
export function HeartIcon({ filled, size = 18 }: Props) {
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
      style={{ display: 'block' }}
    >
      <path d="M12 21s-7-4.5-9.4-9C.7 7.7 3.4 4 7.4 4c1.7 0 3.3.8 4.6 2.1C13.3 4.8 14.9 4 16.6 4c4 0 6.7 3.7 4.8 8-2.4 4.5-9.4 9-9.4 9z"/>
    </svg>
  );
}
