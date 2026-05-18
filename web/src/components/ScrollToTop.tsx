import { useEffect } from 'react';
import { useLocation, useNavigationType } from 'react-router';

/**
 * Resets window scroll to (0, 0) on forward navigation (PUSH/REPLACE).
 *
 * React Router doesn't reset scroll on its own — clicking a list card while
 * scrolled halfway down lands the detail page at that same Y, looking "stuck."
 *
 * Browser-back is left alone (navigationType === 'POP') so returning from a
 * detail to the list restores the previous scroll position the way a
 * standard web app would. Forward clicks always start at the top.
 */
export function ScrollToTop() {
  const { pathname } = useLocation();
  const navType = useNavigationType();
  useEffect(() => {
    if (navType !== 'POP') {
      window.scrollTo(0, 0);
    }
  }, [pathname, navType]);
  return null;
}
