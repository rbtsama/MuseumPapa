import { useState } from 'react';
import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter,
  Button, Input,
} from '@heroui/react';
import { useAuth } from '../auth/store';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Called when the user taps "Already have an account? Sign in" so the
   *  parent can open SignInModal in this slot's place. */
  onSwitchToSignIn?: () => void;
}

/**
 * New-account flow opened from the LandingPromoModal's "Get started" CTA.
 * Brand-green header band matches TopBar + landing visual system.
 *
 * Demo only: signUp persists the new {username, password, displayName} into
 * localStorage's `registered_users` array and immediately signs the user in.
 * No password hashing, no email verification — v0.1 product scope.
 */
export function SignUpModal({ isOpen, onClose, onSwitchToSignIn }: Props) {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const signUp = useAuth(s => s.signUp);

  const reset = () => {
    setUsername('');
    setDisplayName('');
    setPassword('');
    setError(null);
  };

  const handleSubmit = () => {
    const result = signUp(username, password, displayName);
    if (result.ok) {
      reset();
      onClose();
    } else {
      setError(result.error);
    }
  };

  const handleSwitch = () => {
    reset();
    onClose();
    onSwitchToSignIn?.();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalContent>
        <ModalHeader
          style={{
            background: 'var(--g)',
            color: 'var(--white)',
            padding: '14px 18px',
            fontSize: 15,
            fontWeight: 600,
          }}
        >
          Create your account
        </ModalHeader>
        <ModalBody>
          {error && <p style={{ color: 'var(--rd)' }}>{error}</p>}
          <Input
            label="Username"
            value={username}
            onValueChange={setUsername}
            autoFocus
          />
          <Input
            label="Display name (optional)"
            value={displayName}
            onValueChange={setDisplayName}
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onValueChange={setPassword}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
          />
        </ModalBody>
        <ModalFooter
          style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'stretch' }}
        >
          <Button
            onClick={handleSubmit}
            style={{
              background: 'var(--g)', color: 'var(--white)', fontWeight: 600,
              width: '100%',
            }}
          >
            Sign up
          </Button>
          <p style={{ fontSize: 12, color: 'var(--ink-3)', textAlign: 'center', margin: 0 }}>
            Already have an account?{' '}
            <button
              type="button"
              onClick={handleSwitch}
              style={{
                background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
                color: 'var(--g)', fontWeight: 600, fontSize: 12,
              }}
            >
              Sign in →
            </button>
          </p>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
