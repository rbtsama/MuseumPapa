import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VisitInfoSection } from './VisitInfoSection';
import type { Attraction, Hours, Address } from '../../data/types';

const baseHours: Hours = {
  monday: 'closed',
  tuesday: '10:00-17:00',
  wednesday: '10:00-17:00',
  thursday: '10:00-22:00',
  friday: '10:00-22:00',
  saturday: '10:00-17:00',
  sunday: '10:00-17:00',
};

const baseAddress: Address = {
  street: '465 Huntington Ave',
  city: 'Boston',
  state: 'MA',
  zip: '02115',
};

function makeAttraction(over: Partial<Attraction> = {}): Attraction {
  return {
    slug: 'mfa',
    name: 'Museum of Fine Arts',
    address: baseAddress,
    website: 'https://mfa.org',
    phone: '617-267-9300',
    description: null,
    categories: [],
    sources: [],
    prices: [],
    hero_image: null,
    geo: null,
    hours: baseHours,
    reservation: null,
    ...over,
  } as Attraction;
}

describe('VisitInfoSection', () => {
  it('renders address as formatted string from Address object', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    expect(screen.getByText(/465 Huntington Ave/)).toBeInTheDocument();
    expect(screen.getByText(/Boston/)).toBeInTheDocument();
    expect(screen.getByText(/MA 02115/)).toBeInTheDocument();
  });

  it('renders phone and website links', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    expect(screen.getByRole('link', { name: /617-267-9300/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /mfa\.org/ })).toBeInTheDocument();
  });

  it('shows hours summary with closed day listed', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    // Monday is closed → summary should mention "Mon"
    expect(screen.getByText(/Mon/)).toBeInTheDocument();
  });

  it('shows full weekly hours when "See all" clicked', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    // THU label not visible initially
    expect(screen.queryByText(/^THU$/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/See all/i));
    // After expansion, Thu label appears (via weeklyHoursList)
    expect(screen.getByText(/^Thu$/)).toBeInTheDocument();
  });

  it('shows "Hours vary" when hours is null', () => {
    render(<VisitInfoSection attraction={makeAttraction({ hours: null })} />);
    expect(screen.getByText(/Hours vary/)).toBeInTheDocument();
    // No "See all" button when hours unknown
    expect(screen.queryByText(/See all/i)).not.toBeInTheDocument();
  });

  it('shows "Hours vary" when all hours are unknown', () => {
    const allUnknown: Hours = {
      monday: 'unknown', tuesday: 'unknown', wednesday: 'unknown',
      thursday: 'unknown', friday: 'unknown', saturday: 'unknown', sunday: 'unknown',
    };
    render(<VisitInfoSection attraction={makeAttraction({ hours: allUnknown })} />);
    expect(screen.getByText(/Hours vary/)).toBeInTheDocument();
  });

  it('renders null address gracefully (no address section)', () => {
    render(<VisitInfoSection attraction={makeAttraction({ address: null })} />);
    expect(screen.queryByText(/Address/)).not.toBeInTheDocument();
  });
});
