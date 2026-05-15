import { Link } from 'react-router';
import { useAuth } from '../auth/store';
import { useCardpack } from '../stores/cardpack';

interface Props {
  onSignInClick: () => void;
}

export function Banner({ onSignInClick }: Props) {
  const user = useAuth(s => s.currentUser);
  const cards = useCardpack(s => s.pack.cards);
  const hasCards = Object.keys(cards).length > 0;

  if (user && hasCards) return null;

  const text = user
    ? 'Set up your library passes to see your discounts →'
    : 'Add your library pass to unlock discounts →';
  const action = user
    ? <Link to="/settings/passes" style={{ color: 'var(--g)', fontWeight: 500 }}>Open My passes</Link>
    : <button onClick={onSignInClick} style={{
        background: 'transparent', border: 'none', color: 'var(--g)',
        fontWeight: 500, cursor: 'pointer', font: 'inherit',
      }}>Sign in</button>;

  return (
    <div style={{
      borderBottom: '1px solid var(--g-light)',
      background: 'var(--g-pale)',
      padding: '10px 24px',
      fontSize: 13,
      color: 'var(--ink-2)',
      display: 'flex',
      gap: 12,
      alignItems: 'center',
    }}>
      <span style={{ color: 'var(--g)' }}>ⓘ</span>
      <span>{text}</span>
      <span style={{ marginLeft: 'auto' }}>{action}</span>
    </div>
  );
}
