import { useAuth } from '../auth/store';
import { getLibraries } from '../data/load';

export function MyPasses() {
  const user = useAuth(s => s.currentUser);
  if (!user) {
    return <p>Sign in to manage your passes.</p>;
  }
  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '8px' }}>
        My passes
      </h1>
      <p style={{ color: 'var(--ink-3)' }}>
        Signed in as <b>{user.displayName}</b> ({user.persona}).
        Full settings UI lands in plan-4.
      </p>
      <p style={{ color: 'var(--ink-3)', fontSize: '11px', marginTop: '8px' }}>
        {getLibraries().length} libraries available.
      </p>
    </div>
  );
}
