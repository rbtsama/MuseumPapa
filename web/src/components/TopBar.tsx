import { useState } from 'react';
import { Link } from 'react-router';
import { Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/react';
import { useAuth } from '../auth/store';
import { SignInModal } from './SignInModal';

export function TopBar() {
  const user = useAuth(s => s.currentUser);
  const signOut = useAuth(s => s.signOut);
  const [signInOpen, setSignInOpen] = useState(false);

  return (
    <header style={{
      borderBottom: '1px solid var(--rule)',
      background: 'var(--white)',
      padding: '12px 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <Link to="/" className="font-serif" style={{ fontSize: '20px', color: 'var(--g)' }}>
        MuseumPass MA
      </Link>
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
      <SignInModal isOpen={signInOpen} onClose={() => setSignInOpen(false)} />
    </header>
  );
}
