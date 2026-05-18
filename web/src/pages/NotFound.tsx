import { Link } from 'react-router';

export function NotFound() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      <div style={{ marginBottom: 12 }}>
        <Link to="/" style={{ color: 'var(--ink-3)', fontSize: 13 }}>← Back to attractions</Link>
      </div>
      <h1 style={{ fontSize: 22, color: 'var(--ink-2)', fontWeight: 700 }}>404</h1>
      <p style={{ color: 'var(--ink-3)' }}>This page doesn't exist.</p>
    </div>
  );
}
