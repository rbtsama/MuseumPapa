import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TodayFactsCard } from './TodayFactsCard';
import type { Attraction } from '../../data/types';

function makeAttraction(over: Partial<Attraction> = {}): Attraction {
  return {
    slug: 'mfa',
    museum_name: 'MFA',
    address: '',
    website: '',
    phone: null,
    description: null,
    categories: [],
    sources: [],
    original_price: {
      age_pricing: {
        adult: { price: 27, min_age: null, max_age: null },
        youth: null,
        child: null,
        senior: null,
        free_under_age: 7,
      },
      identity_pricing: { student: null, educator: null, military: null },
      family: null,
      notes: null,
      source_url: null,
    },
    hero_image: null,
    geo: null,
    hours: null,
    museum_reservation: null,
    ...over,
  } as Attraction;
}

describe('TodayFactsCard', () => {
  it('renders today heading and price line', () => {
    render(<TodayFactsCard attraction={makeAttraction()} todayIso="2026-05-18" />);
    expect(screen.getByText(/Today/)).toBeInTheDocument();
    expect(screen.getByText(/Adult \$27/)).toBeInTheDocument();
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
  });

  it('shows reservation banner when reservation present', () => {
    const a = makeAttraction({
      museum_reservation: { required: true, url: null },
    });
    render(<TodayFactsCard attraction={a} todayIso="2026-05-18" />);
    expect(screen.getByText(/reservation/i)).toBeInTheDocument();
  });
});
