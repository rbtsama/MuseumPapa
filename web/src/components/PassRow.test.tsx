import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PassRow } from './PassRow';
import type { Pass, Library, Coupon } from '../data/types';

const baseCoupon: Coupon = {
  capacity: { kind: 'people', n: 4 },
  audience_policies: [
    { audience: 'Everyone', age_range: { min: null, max: null }, count: null, form: 'free', value: null },
  ],
};

function makePass(over: Partial<Pass> = {}): Pass {
  return {
    library_id: 'wakefield',
    attraction_slug: 'test',
    pass_type: 'digital',
    pickup_method: 'digital',
    coupon: baseCoupon,
    availability: null,
    restrictions: null,
    ...over,
  } as Pass;
}

const libWakefield: Library = {
  id: 'wakefield', name: 'Wakefield Public Library', town: 'Wakefield',
} as Library;

describe('PassRow', () => {
  it('renders digital pass with Email chip + library name', () => {
    render(
      <PassRow pass={makePass()} library={libWakefield} distanceMi={null} onBook={() => {}} />,
    );
    expect(screen.getByText(/Email/)).toBeInTheDocument();
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
  });

  it('renders pickup pass with chip + distance + library', () => {
    render(
      <PassRow
        pass={makePass({ pass_type: 'physical-coupon' })}
        library={libWakefield}
        distanceMi={7.2}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/Pickup 7mi/)).toBeInTheDocument();
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
  });

  it('invokes onBook when Book button clicked', () => {
    const onBook = vi.fn();
    render(
      <PassRow pass={makePass()} library={libWakefield} distanceMi={null} onBook={onBook} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /book/i }));
    expect(onBook).toHaveBeenCalledTimes(1);
  });
});
