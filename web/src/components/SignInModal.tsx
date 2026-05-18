import { useState } from 'react';
import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter,
  Button, Input,
} from '@heroui/react';
import { useAuth } from '../auth/store';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Optional: lets the parent open SignUpModal when the user taps the
   *  "New here? Sign up" link at the bottom. */
  onSwitchToSignUp?: () => void;
}

export function SignInModal({ isOpen, onClose, onSwitchToSignUp }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const signIn = useAuth(s => s.signIn);

  const handleSubmit = () => {
    const result = signIn(username, password);
    if (result.ok) {
      setUsername('');
      setPassword('');
      setError(null);
      onClose();
    } else {
      setError(result.error);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalContent>
        {/* Brand-green title band keeps the modal in the same visual system
            as the TopBar / landing promo / Save buttons. */}
        <ModalHeader
          style={{
            background: 'var(--g)',
            color: 'var(--white)',
            padding: '14px 18px',
            fontSize: 15,
            fontWeight: 600,
          }}
        >
          Sign in to MuseumPapa
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
            label="Password"
            type="password"
            value={password}
            onValueChange={setPassword}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
          />
          {import.meta.env.DEV && (
            <p style={{ fontSize: '11px', color: 'var(--ink-3)' }}>
              Demo accounts: alex / rbt / admin (password = username)
            </p>
          )}
        </ModalBody>
        <ModalFooter
          style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'stretch' }}
        >
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <Button variant="light" onClick={onClose}>Cancel</Button>
            <Button
              onClick={handleSubmit}
              style={{ background: 'var(--g)', color: 'var(--white)', fontWeight: 600 }}
            >
              Sign in
            </Button>
          </div>
          {onSwitchToSignUp && (
            <p style={{ fontSize: 12, color: 'var(--ink-3)', textAlign: 'center', margin: 0 }}>
              New here?{' '}
              <button
                type="button"
                onClick={() => { setUsername(''); setPassword(''); setError(null); onClose(); onSwitchToSignUp(); }}
                style={{
                  background: 'transparent', border: 'none', padding: 0, cursor: 'pointer',
                  color: 'var(--g)', fontWeight: 600, fontSize: 12,
                }}
              >
                Sign up →
              </button>
            </p>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
