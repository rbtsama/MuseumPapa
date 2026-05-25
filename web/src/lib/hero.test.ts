import { describe, it, expect } from 'vitest';
import { heroSrc } from './hero';

describe('heroSrc', () => {
  it('upgrades a legacy http hero image to https (avoid mixed-content block)', () => {
    expect(heroSrc({ hero_image: 'http://example.org/a.jpg', categories: ['art'] }))
      .toBe('https://example.org/a.jpg');
  });

  it('leaves an https hero image untouched', () => {
    expect(heroSrc({ hero_image: 'https://example.org/a.jpg', categories: ['art'] }))
      .toBe('https://example.org/a.jpg');
  });

  it('falls back to the category placeholder when no hero image', () => {
    expect(heroSrc({ hero_image: null, categories: ['Science'] }))
      .toBe('/placeholders/science.svg');
  });

  it('falls back to default.svg for a canonical category without its own SVG', () => {
    expect(heroSrc({ hero_image: null, categories: ['Performance'] }))
      .toBe('/placeholders/default.svg');
  });

  it('falls back to default.svg when no category matches', () => {
    expect(heroSrc({ hero_image: null, categories: [] }))
      .toBe('/placeholders/default.svg');
  });
});
