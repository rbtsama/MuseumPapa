import { getAttractions } from '../data/load';

export function AttractionsList() {
  const attractions = getAttractions();
  return (
    <div>
      <h1 className="font-serif" style={{ fontSize: '24px', marginBottom: '12px' }}>
        Attractions
      </h1>
      <p style={{ color: 'var(--ink-3)', marginBottom: '12px' }}>
        Loaded {attractions.length} attractions. (List UI lands in plan-4.)
      </p>
      <ul>
        {attractions.slice(0, 10).map(a => (
          <li key={a.slug} style={{ padding: '4px 0' }}>
            <a href={`/attractions/${a.slug}`} style={{ color: 'var(--g)' }}>
              {a.museum_name}
            </a>
            <span style={{ color: 'var(--ink-3)', marginLeft: '8px' }}>
              · {a.sources.length} libraries
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
