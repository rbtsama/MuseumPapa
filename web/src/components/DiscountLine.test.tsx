import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { DiscountLine } from './DiscountLine';
import type { Discount, Policy } from '../data/types';

function makeDiscount(klass: string, label: string, raw = ''): Discount {
  return { class: klass as Discount['class'], label, raw };
}

function makePolicy(overrides: Partial<Policy> = {}): Policy {
  return {
    max_people: null,
    max_adults: null,
    max_children: null,
    free_under_age: null,
    savings_per_person_usd: null,
    discount_percent: null,
    discount_dollar_off: null,
    eligibility_tags: [],
    exclusions: [],
    boosts: [],
    notes: null,
    raw: null,
    ...overrides,
  };
}

describe('DiscountLine', () => {
  it('free discount with no policy shows "Free" price', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('free', 'Free')}
        policy={null}
        adult={30}
      />
    );
    expect(screen.getByText('Free')).toBeInTheDocument();
  });

  it('half discount with max_people=4 shows qualifier "up to 4 people"', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('half', '50% off')}
        policy={makePolicy({ max_people: 4 })}
        adult={30}
      />
    );
    expect(screen.getByText('up to 4 people')).toBeInTheDocument();
  });

  it('half discount with adults_only eligibility shows "adults only" qualifier', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('half', '50% off')}
        policy={makePolicy({ eligibility_tags: ['adults_only'] })}
        adult={30}
      />
    );
    expect(screen.getByText('adults only')).toBeInTheDocument();
  });

  it('dollar-off discount with savings_per_person shows detail text', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('dollar-off', '$5 off')}
        policy={makePolicy({ savings_per_person_usd: 5 })}
        adult={30}
      />
    );
    // savings_per_person_usd blocks dollar projection, shows primary label
    expect(screen.getByText('$5 off')).toBeInTheDocument();
    // detail shows savings per person
    expect(screen.getByText('save $5 per person')).toBeInTheDocument();
  });

  it('free discount with vehicle eligibility shows "per vehicle" qualifier', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('free', 'Free')}
        policy={makePolicy({ eligibility_tags: ['vehicle'] })}
        adult={30}
      />
    );
    expect(screen.getByText('per vehicle')).toBeInTheDocument();
  });

  it('policy with free_under_age shows detail "Free under 2"', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('free', 'Free')}
        policy={makePolicy({ free_under_age: 2 })}
        adult={30}
      />
    );
    expect(screen.getByText('Free under 2')).toBeInTheDocument();
  });

  it('shows strikethrough original price when dollar reduction applies', () => {
    renderApp(
      <DiscountLine
        discount={makeDiscount('half', '50% off')}
        policy={null}
        adult={30}
      />
    );
    // finalPrice=15 (half of 30), originalPrice=30 shown with line-through
    expect(screen.getByText('$30')).toBeInTheDocument();
    expect(screen.getByText('$15')).toBeInTheDocument();
  });
});
