import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from '../../test-utils';
import { HeroBanner } from './HeroBanner';

describe('HeroBanner', () => {
  it('renders museum name and image', () => {
    renderApp(
      <HeroBanner
        imageSrc="/test.jpg"
        museumName="Museum of Fine Arts"
        town="Boston"
        favoriteSlug="mfa"
      />,
    );
    expect(screen.getByText('Museum of Fine Arts')).toBeInTheDocument();
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img).not.toBeNull();
    expect(img.src).toContain('/test.jpg');
  });

  it('does not render its own back link (TopBar carries the sticky back affordance)', () => {
    renderApp(
      <HeroBanner imageSrc="/x.jpg" museumName="X" favoriteSlug="x" />,
    );
    expect(screen.queryByRole('link', { name: /back/i })).toBeNull();
  });
});
