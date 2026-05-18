import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';
import { useAuth } from '../auth/store';
import { SignInModal } from './SignInModal';
import { ZipPill } from './ZipPill';
import { ChevronLeftIcon } from './icons';

/**
 * Solid brand-green TopBar (Trip.com / Booking.com pattern) so the entire
 * top of the viewport is one branded color. Paired with `<meta name="theme-color">`
 * the browser chrome (URL bar) matches — full visual continuity from the
 * status bar down into the app.
 *
 * On non-root routes (detail page, settings, 404), a back chevron appears
 * before the brand wordmark. Because the TopBar itself is sticky, the back
 * affordance stays in view at any scroll position — no need for a per-page
 * floating back button.
 */
export function TopBar() {
  const user = useAuth(s => s.currentUser);
  const signOut = useAuth(s => s.signOut);
  const [signInOpen, setSignInOpen] = useState(false);
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const onSubPage = pathname !== '/';

  const handleBack = () => {
    // history.length > 1 = there's something to go back to. If the user opened
    // the detail URL directly (e.g. paste-in), navigate('/') instead so they
    // don't get stuck on a blank previous page.
    if (window.history.length > 1) navigate(-1);
    else navigate('/');
  };

  return (
    <header
      className="px-3 sm:px-4 py-2.5 flex items-center justify-between gap-3 sticky top-0"
      style={{ background: 'var(--g)', zIndex: 50 }}
    >
      <div className="flex items-center gap-2 min-w-0">
        {onSubPage && (
          <button
            type="button"
            onClick={handleBack}
            aria-label="Back"
            className="inline-flex items-center justify-center flex-shrink-0"
            style={{
              width: 32, height: 32, borderRadius: 6,
              background: 'rgba(255,255,255,0.15)', color: 'var(--white)',
              border: 'none', cursor: 'pointer',
            }}
          >
            <ChevronLeftIcon />
          </button>
        )}
        <Link to="/" className="font-serif truncate flex-shrink-0"
          style={{ fontSize: 16, color: 'var(--white)' }}>
          MuseumPapa
        </Link>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 flex-shrink min-w-0">
        <ZipPill onDark />
        {user ? (
          <Dropdown>
            <DropdownTrigger>
              <button
                type="button"
                style={{
                  background: 'rgba(255,255,255,0.15)',
                  color: 'var(--white)',
                  padding: '5px 10px',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 500,
                  border: 'none',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.displayName}
              </button>
            </DropdownTrigger>
            <DropdownMenu aria-label="user menu">
              <DropdownItem key="passes" as={Link} to="/settings/passes">My library cards</DropdownItem>
              <DropdownItem key="signout" onClick={signOut} className="text-danger">
                Sign out
              </DropdownItem>
            </DropdownMenu>
          </Dropdown>
        ) : (
          <button
            type="button"
            onClick={() => setSignInOpen(true)}
            style={{
              background: 'var(--white)',
              color: 'var(--g)',
              padding: '6px 14px',
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Sign in
          </button>
        )}
      </div>
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </header>
  );
}
