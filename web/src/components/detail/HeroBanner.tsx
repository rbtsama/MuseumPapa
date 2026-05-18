import { FavoriteButton } from '../FavoriteButton';
import { PinIcon } from '../icons';

interface Props {
  imageSrc: string;
  museumName: string;
  town?: string;
  favoriteSlug: string;
}

export function HeroBanner({ imageSrc, museumName, town, favoriteSlug }: Props) {
  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <img
        src={imageSrc}
        alt={museumName}
        style={{
          width: '100%',
          height: 180,
          objectFit: 'cover',
          display: 'block',
          background: 'var(--paper)',
        }}
      />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.55), transparent 55%)',
          pointerEvents: 'none',
        }}
      />
      {/* Back affordance moved to TopBar (sticky, always reachable while
          scrolling). Heart stays as a hero overlay since it's contextual to
          this attraction. */}
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 2 }}>
        <FavoriteButton slug={favoriteSlug} variant="overlay" />
      </div>
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 1,
          padding: 14,
          color: 'var(--white)',
        }}
      >
        <h1
          className="font-serif"
          style={{
            fontSize: 20,
            lineHeight: 1.2,
            fontWeight: 700,
            margin: 0,
            color: 'var(--white)',
            textShadow: '0 1px 3px rgba(0,0,0,0.5)',
          }}
        >
          {museumName}
        </h1>
        {town && (
          <div style={{ fontSize: 12, marginTop: 2, opacity: 0.9 }} className="inline-flex items-center gap-1"><PinIcon />{town}</div>
        )}
      </div>
    </div>
  );
}
