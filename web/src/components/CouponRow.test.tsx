import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CouponRow } from './CouponRow';
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

describe('CouponRow', () => {
  it('renders type pill, location text, and Book button for a digital pass', () => {
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        distanceMi={null}
        userHasCard
        onBook={() => {}}
      />,
    );
    // Location text for digital = library name
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
    // PassTypeLabel for `digital` renders some label text
    expect(screen.getByRole('button', { name: /book/i })).toBeInTheDocument();
    // Coupon form=free → "FREE" surfaces from CouponLine
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
  });

  it('calls onBook when Book is clicked', () => {
    const onBook = vi.fn();
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        distanceMi={null}
        userHasCard
        onBook={onBook}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /book/i }));
    expect(onBook).toHaveBeenCalledTimes(1);
  });

  it('shows the "no card" sub-label when userHasCard=false', () => {
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        distanceMi={null}
        userHasCard={false}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/no card/i)).toBeInTheDocument();
  });
});
