import { useParams } from 'react-router';
import { getAttractionBySlug, getPassesForAttraction } from '../data/load';

export function AttractionDetail() {
  const { slug } = useParams<{ slug: string }>();
  if (!slug) return <p>Missing slug.</p>;
  const attraction = getAttractionBySlug(slug);
  if (!attraction) return <p>Attraction "{slug}" not found.</p>;
  const passes = getPassesForAttraction(slug);

  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '8px' }}>
        {attraction.museum_name}
      </h1>
      <p style={{ color: 'var(--ink-3)', marginBottom: '12px' }}>
        {attraction.address} · {passes.length} passes available
      </p>
      <pre style={{
        background: 'var(--paper)', padding: '12px', fontSize: '11px',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}>
        {JSON.stringify(attraction, null, 2)}
      </pre>
    </div>
  );
}
