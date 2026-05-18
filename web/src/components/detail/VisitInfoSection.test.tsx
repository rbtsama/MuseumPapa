import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VisitInfoSection } from './VisitInfoSection';
import type { Attraction } from '../../data/types';

function makeAttraction(): Attraction {
  return {
    slug: 'mfa',
    museum_name: 'MFA',
    address: '465 Huntington Ave, Boston, MA 02115',
    website: 'https://mfa.org',
    phone: '617-267-9300',
    description: null,
    categories: [],
    sources: [],
    original_price: null,
    hero_image: null,
    geo: null,
    hours: {
      status: 'ok',
      regular_hours: {
        sun: '10am – 5pm',
        mon: 'Closed',
        tue: '10am – 5pm',
        wed: '10am – 5pm',
        thu: '10am – 10pm',
        fri: '10am – 10pm',
        sat: '10am – 5pm',
      },
      notes: null,
      source_url: null,
    },
    museum_reservation: null,
  } as Attraction;
}

describe('VisitInfoSection', () => {
  it('renders address, phone, website', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    expect(screen.getByText(/465 Huntington/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /617-267-9300/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /mfa\.org/ })).toBeInTheDocument();
  });

  it('shows full weekly hours when See all clicked', () => {
    render(<VisitInfoSection attraction={makeAttraction()} />);
    expect(screen.queryByText(/THU/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(/See all/i));
    expect(screen.getByText(/THU/i)).toBeInTheDocument();
  });
});
