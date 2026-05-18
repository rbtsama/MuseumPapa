import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { AttractionCard } from './AttractionCard';
import { useFavorites } from '../stores/favorites';
import type { Attraction, Pass, Library } from '../data/types';
import type { PickedTag } from '../lib/tag-algorithm';

beforeEach(() => {
  useFavorites.setState({ slugs: new Set() });
});

function makeAttraction(overrides: Partial<Attraction> = {}): Attraction {
  return {
    slug: 'test-zoo',
    museum_name: 'Test Zoo',
    address: '100 Zoo Rd, Boston, MA 02101',
    website: 'https://example.com',
    phone: null,
    description: null,
    categories: ['Animals', 'Family'],
    sources: [],
    original_price: {
      age_pricing: {
        adult: { price: 30, min_age: null, max_age: null },
        youth: null,
        child: { price: 20, min_age: null, max_age: null },
        senior: null,
        free_under_age: null,
      },
      identity_pricing: {
        student: null,
        educator: null,
        military: null,
      },
      family: null,
      notes: null,
      source_url: null,
    },
    hero_image: null,
    geo: null,
    hours: null,
    museum_reservation: null,
    ...overrides,
  };
}

function makePass(overrides: Partial<Pass> = {}): Pass {
  return {
    library_id: 'wakefield',
    attraction_slug: 'test-zoo',
    pass_type: 'digital',
    pass_type_raw: 'digital',
    pickup_method: 'digital',
    pickup_branches: [],
    coupon: {
      capacity: { kind: 'people', n: 4 },
      audience_policies: [{ audience: 'Everyone', age_range: null, count: null, form: 'free', value: null }],
    },
    restrictions: null,
    source_url: 'https://example.com/book',
    availability: null,
    ...overrides,
  };
}

function makeLibrary(overrides: Partial<Library> = {}): Library {
  return {
    id: 'wakefield',
    name: 'Wakefield Public Library',
    town: 'Wakefield',
    network: 'assabet',
    platform: 'assabet',
    card_page: 'https://wakefield.com/cards',
    eligibility: 'Wakefield residents',
    supports_availability: true,
    address: null,
    geo: null,
    ...overrides,
  };
}

function makePickedTag(passOverrides: Partial<Pass> = {}, libOverrides: Partial<Library> = {}): PickedTag {
  return {
    pass: makePass(passOverrides),
    library: makeLibrary(libOverrides),
    distanceMi: null,
  };
}

describe('AttractionCard', () => {
  it('renders attraction name', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText('Test Zoo')).toBeInTheDocument();
  });

  it('renders guest state with sign-in CTA', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="guest"
      />
    );
    expect(screen.getByText(/Sign in to see/)).toBeInTheDocument();
  });

  it('renders no-cards state with add-card CTA pointing to /settings/passes', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="no_cards"
      />
    );
    const link = screen.getByText(/Add a library card or Library Pass/);
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', '/settings/passes');
  });

  it('renders no-matching-coupon hint when user has cards but no passes match', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/None of your library cards cover this attraction/)).toBeInTheDocument();
  });

  it('renders pass options for logged-in user', () => {
    const tags = [makePickedTag()];
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={tags}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Book')).toBeInTheDocument();
  });

  it('clicking Book button fires onBookPass with the pass', () => {
    const onBookPass = vi.fn();
    const pass = makePass();
    const tags: PickedTag[] = [{ pass, library: makeLibrary(), distanceMi: null }];
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={tags}
        cardpackState="has_cards"
        onBookPass={onBookPass}
      />
    );
    const bookBtn = screen.getByText('Book');
    fireEvent.click(bookBtn);
    expect(onBookPass).toHaveBeenCalledWith(pass);
  });

  it('renders the no-coupons message when no tags and user has cards', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    // New copy: explicit reason — the user's cards don't yield a coupon here.
    expect(screen.getByText(/None of your library cards cover this attraction/)).toBeInTheDocument();
  });

  it('renders closed state when closedToday=true', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[makePickedTag()]}
        cardpackState="has_cards"
        closedToday
      />
    );
    expect(screen.getByText('Closed')).toBeInTheDocument();
    // Book buttons should not appear when closed
    expect(screen.queryByText('Book')).not.toBeInTheDocument();
  });

  it('renders location from address', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/Boston, MA/)).toBeInTheDocument();
  });

  it('renders adult price from original_price', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    // $30 adult price shown in admission section
    expect(screen.getByText('$30')).toBeInTheDocument();
  });

  it('renders the "FREE age<N" hint when free_under_age is set', () => {
    const a = makeAttraction();
    a.original_price!.age_pricing.free_under_age = 3;
    renderApp(
      <AttractionCard
        attraction={a}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText('FREE')).toBeInTheDocument();
    expect(screen.getByText(/age <3/)).toBeInTheDocument();
  });

  it('does not render the FREE-age hint when free_under_age is null', () => {
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={[]}
        cardpackState="has_cards"
      />
    );
    expect(screen.queryByText(/age </)).not.toBeInTheDocument();
  });

  it('shows "+ N more" when more than 3 tags (cap matches pickTags maxTags=3)', () => {
    const tags = Array.from({ length: 5 }, (_, i) =>
      makePickedTag({ library_id: `lib-${i}`, pass_type: 'physical-coupon' }, { id: `lib-${i}`, town: `Town${i}` })
    );
    renderApp(
      <AttractionCard
        attraction={makeAttraction()}
        pickedTags={tags}
        cardpackState="has_cards"
      />
    );
    expect(screen.getByText(/\+ 2 more coupons/)).toBeInTheDocument();
  });
});
