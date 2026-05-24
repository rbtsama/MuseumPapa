import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { AttractionCard } from './AttractionCard';
import { useFavorites } from '../stores/favorites';
import type { Attraction, Pass } from '../data/types';
import type { RecommendedPass } from '../lib/recommend';
import type { PassVerdict } from '../lib/eligibility';

const navigateMock = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => navigateMock };
});

beforeEach(() => {
  useFavorites.setState({ slugs: new Set() });
  navigateMock.mockClear();
});

function makeAttraction(overrides: Partial<Attraction> = {}): Attraction {
  return {
    slug: 'test-zoo',
    name: 'Test Zoo',
    address: { street: '100 Zoo Rd', city: 'Boston', state: 'MA', zip: '02101' },
    website: 'https://example.com',
    phone: null,
    description: null,
    categories: ['Animals', 'Family'],
    sources: [],
    prices: [
      { audience: 'adult', price: 30, age_range: null },
      { audience: 'child', price: 20, age_range: null },
    ],
    hero_image: null,
    geo: null,
    hours: null,
    reservation: null,
    ...overrides,
  };
}

function makePass(overrides: Partial<Pass> = {}): Pass {
  return {
    library_id: 'wakefield',
    attraction_slug: 'test-zoo',
    pass_form: 'digital_email',
    available_at_branches: 'all',
    coupon: {
      capacity: { kind: 'people', n: 4 },
      audience_policies: [{ audience: 'Everyone', form: 'free', value: null }],
    },
    restrictions: null,
    residency_restriction: { restricted: 'no', scope: null },
    availability: {},
    source_url: 'https://example.com/book',
    ...overrides,
  };
}

function makeVerdict(overrides: Partial<PassVerdict> = {}): PassVerdict {
  return {
    eligible: true,
    reasons: [],
    warnings: [],
    ...overrides,
  };
}

function makeRec(passOverrides: Partial<Pass> = {}, verdictOverrides: Partial<PassVerdict> = {}): RecommendedPass {
  return {
    pass: makePass(passOverrides),
    verdict: makeVerdict(verdictOverrides),
    score: 60,
  };
}

describe('AttractionCard', () => {
  it('renders attraction name', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText('Test Zoo')).toBeInTheDocument();
  });

  it('renders guest state with sign-in CTA', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="guest"
      />
    );
    expect(screen.getByText(/Sign in to see/)).toBeInTheDocument();
  });

  it('renders no-cards state with add-card CTA pointing to /settings/passes', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="no_cards"
      />
    );
    const btn = screen.getByText(/Add a library card or Library Pass/);
    expect(btn).toBeInTheDocument();
    const buttonEl = btn.closest('button');
    expect(buttonEl).not.toBeNull();
    fireEvent.click(buttonEl!);
    expect(navigateMock).toHaveBeenCalledWith('/settings/passes');
  });

  it('renders no-matching-coupon hint when user has cards but no passes match', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/None of your library cards cover this attraction/)).toBeInTheDocument();
  });

  it('renders eligible rec: couponSummary label visible and Book button enabled', () => {
    const rec = makeRec({}, { eligible: true, warnings: [] });
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[rec]}
        cardpackState="has_cards"
      />
    );
    // couponSummary for a 'free' form is "FREE"
    expect(screen.getByText('FREE')).toBeInTheDocument();
    const bookBtn = screen.getByRole('button', { name: /book/i });
    expect(bookBtn).not.toBeDisabled();
  });

  it('clicking Book button fires onBookPass with the pass when eligible', () => {
    const onBookPass = vi.fn();
    const pass = makePass();
    const rec: RecommendedPass = { pass, verdict: makeVerdict(), score: 60 };
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[rec]}
        cardpackState="has_cards"
        onBookPass={onBookPass}
      />
    );
    const bookBtn = screen.getByRole('button', { name: /book/i });
    fireEvent.click(bookBtn);
    expect(onBookPass).toHaveBeenCalledWith(pass);
  });

  it('renders blocked rec: shows 不可领 badge and Book button is disabled', () => {
    const rec = makeRec({}, {
      eligible: false,
      blockedLayer: 'L1',
      reasons: ['你没有 assabet 网络的卡'],
      warnings: [],
    });
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[rec]}
        cardpackState="has_cards"
      />
    );
    // Badge text visible
    expect(screen.getAllByText('不可领').length).toBeGreaterThan(0);
    // Book button disabled
    const bookBtn = screen.getByRole('button', { name: /book/i });
    expect(bookBtn).toBeDisabled();
  });

  it('blocked Book button does NOT call onBookPass', () => {
    const onBookPass = vi.fn();
    const rec = makeRec({}, {
      eligible: false,
      blockedLayer: 'L1',
      reasons: ['你没有 assabet 网络的卡'],
      warnings: [],
    });
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[rec]}
        cardpackState="has_cards"
        onBookPass={onBookPass}
      />
    );
    const bookBtn = screen.getByRole('button', { name: /book/i });
    fireEvent.click(bookBtn);
    expect(onBookPass).not.toHaveBeenCalled();
  });

  it('renders eligible rec with warning: shows 资格待确认 badge', () => {
    const rec = makeRec({}, {
      eligible: true,
      warnings: ['取 pass 资格未确认'],
    });
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[rec]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText('资格待确认')).toBeInTheDocument();
    // Book button still active when eligible (even with warning)
    const bookBtn = screen.getByRole('button', { name: /book/i });
    expect(bookBtn).not.toBeDisabled();
  });

  it('renders closed state when closedToday=true', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[makeRec()]}
        cardpackState="has_cards"
        closedToday
      />
    );
    expect(screen.getByText('Closed')).toBeInTheDocument();
    // Book buttons should not appear when closed
    expect(screen.queryByRole('button', { name: /book/i })).not.toBeInTheDocument();
  });

  it('renders location from address city', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/Boston, MA/)).toBeInTheDocument();
  });

  it('renders adult price from prices array', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={[]}
        cardpackState="has_cards"
      />
    );
    // $30 adult price shown in admission section
    expect(screen.getByText('$30')).toBeInTheDocument();
  });

  it('shows "+ N more options" when more than 3 recommendations', () => {
    const recs: RecommendedPass[] = Array.from({ length: 5 }, (_, i) =>
      makeRec({ library_id: `lib-${i}`, pass_form: 'physical_coupon' }, {})
    );
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        recommendations={recs}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/\+ 2 more options/)).toBeInTheDocument();
  });
});
