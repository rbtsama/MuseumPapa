import { useState } from 'react';
import { Link } from 'react-router';
import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';
import { useAuth } from '../auth/store';
import { SignInModal } from './SignInModal';
import { ZipPill } from './ZipPill';

export function TopBar() {
  const user = useAuth(s => s.currentUser);
  const signOut = useAuth(s => s.signOut);
  const [signInOpen, setSignInOpen] = useState(false);

  return (
    <header
      className="px-3 sm:px-4 py-2.5 flex items-center justify-between gap-3"
      style={{ borderBottom: '1px solid var(--rule)', background: 'var(--white)' }}
    >
      <Link to="/" className="font-serif truncate flex-shrink-0" style={{ fontSize: 17, color: 'var(--g)' }}>
        MuseumPass MA
      </Link>

      <div className="flex items-center gap-2 sm:gap-3 flex-shrink min-w-0">
        <ZipPill />
        {user ? (
          <Dropdown>
            <DropdownTrigger>
              <Button variant="light" size="sm">{user.displayName}</Button>
            </DropdownTrigger>
            <DropdownMenu aria-label="user menu">
              <DropdownItem key="passes" href="/settings/passes">My passes</DropdownItem>
              <DropdownItem key="signout" onClick={signOut} className="text-danger">
                Sign out
              </DropdownItem>
            </DropdownMenu>
          </Dropdown>
        ) : (
          <Button size="sm" color="primary" onClick={() => setSignInOpen(true)}>
            Sign in
          </Button>
        )}
      </div>
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </header>
  );
}
