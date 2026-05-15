import { useState } from 'react';
import {
  Modal, ModalContent, ModalHeader, ModalBody, ModalFooter,
  Button, Input,
} from '@heroui/react';
import { useAuth } from '../auth/store';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function SignInModal({ isOpen, onClose }: Props) {
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
        <ModalHeader>Sign in to MuseumPapa</ModalHeader>
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
          <p style={{ fontSize: '11px', color: 'var(--ink-3)' }}>
            Demo accounts: alex / rbt / admin (password = username)
          </p>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onClick={onClose}>Cancel</Button>
          <Button color="primary" onClick={handleSubmit}>Sign in</Button>
          <Button disabled title="Sign-up coming soon">Sign up</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
