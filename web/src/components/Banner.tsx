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
    ? 'Add your library passes to unlock discounts'
    : 'Add your library passes to unlock discounts';
  const action = user
    ? <Link to="/settings/passes" className="font-medium whitespace-nowrap"
        style={{ color: 'var(--g)' }}>Manage passes →</Link>
    : <button onClick={onSignInClick} className="font-medium whitespace-nowrap"
        style={{ background: 'transparent', border: 'none', color: 'var(--g)', cursor: 'pointer', font: 'inherit' }}>
        Sign in →
      </button>;

  return (
    <div className="px-4 sm:px-6 py-2.5 text-[13px] flex flex-wrap gap-x-3 gap-y-1 items-center"
      style={{
        borderBottom: '1px solid var(--g-light)',
        background: 'var(--g-pale)',
        color: 'var(--ink-2)',
      }}>
      <span style={{ color: 'var(--g)' }} aria-hidden>ⓘ</span>
      <span className="flex-grow min-w-0">{text}</span>
      {action}
    </div>
  );
}
