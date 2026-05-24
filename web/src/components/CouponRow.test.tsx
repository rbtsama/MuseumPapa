import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CouponRow } from './CouponRow';
import type { Pass, Library, Coupon } from '../data/types';
import type { PassVerdict } from '../lib/eligibility';

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
    pass_form: 'digital_email',
    available_at_branches: 'all',
    coupon: baseCoupon,
    availability: {},
    restrictions: null,
    residency_restriction: { restricted: 'no', scope: null },
    ...over,
  } as Pass;
}

const eligibleVerdict: PassVerdict = { eligible: true, reasons: [], warnings: [] };
const warnVerdict: PassVerdict = { eligible: true, reasons: [], warnings: ['Pass pickup eligibility not confirmed'] };
const ineligibleVerdict: PassVerdict = { eligible: false, blockedLayer: 'L1', reasons: ['No NOBLE network card'], warnings: [] };

const libWakefield: Library = {
  id: 'wakefield', name: 'Wakefield Public Library', town: 'Wakefield',
} as Library;

describe('CouponRow', () => {
  it('renders type pill, location text, and Book button for an eligible digital pass', () => {
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={null}
        onBook={() => {}}
      />,
    );
    // Location text for digital = library name
    expect(screen.getByText(/Wakefield Public Library/)).toBeInTheDocument();
    // PassTypeLabel for `digital_email` renders "Email"
    expect(screen.getByText('Email')).toBeInTheDocument();
    // Coupon form=free → "FREE" surfaces from CouponLine
    expect(screen.getByText(/FREE/)).toBeInTheDocument();
    // Book button is enabled
    const btn = screen.getByRole('button', { name: /book/i });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it('calls onBook when Book is clicked (eligible)', () => {
    const onBook = vi.fn();
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={null}
        onBook={onBook}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /book/i }));
    expect(onBook).toHaveBeenCalledTimes(1);
  });

  it('disables Book button and shows reason chip for ineligible pass', () => {
    const onBook = vi.fn();
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        verdict={ineligibleVerdict}
        distanceMi={null}
        onBook={onBook}
      />,
    );
    const btn = screen.getByRole('button', { name: /book/i });
    expect(btn).toBeDisabled();
    // "Not eligible" chip visible
    expect(screen.getByText(/Not eligible/)).toBeInTheDocument();
    // Clicking disabled button does not call onBook
    fireEvent.click(btn);
    expect(onBook).not.toHaveBeenCalled();
  });

  it('shows warning chip for pass with eligible verdict but warnings', () => {
    render(
      <CouponRow
        pass={makePass()}
        library={libWakefield}
        verdict={warnVerdict}
        distanceMi={null}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/Pass pickup eligibility not confirmed/)).toBeInTheDocument();
    // Book button still enabled
    expect(screen.getByRole('button', { name: /book/i })).not.toBeDisabled();
  });

  it('shows distance for non-digital pass when distanceMi provided', () => {
    render(
      <CouponRow
        pass={makePass({ pass_form: 'physical_circ' })}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={7.8}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/8 mi/)).toBeInTheDocument();
    expect(screen.getByText(/Wakefield/)).toBeInTheDocument();
  });

  it('renders pickup/return reminder for physical_circ pass', () => {
    render(
      <CouponRow
        pass={makePass({ pass_form: 'physical_circ' })}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={null}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/Pick up and return at the library/)).toBeInTheDocument();
  });

  it('renders booking_frequency_limit note when present', () => {
    const pass = makePass({
      pass_form: 'physical_circ',
      restrictions: {
        blackout: [], blackout_recurring: [], weekdays_only: false, seasonal: null,
        advance_booking_required: false, advance_booking_hours: null,
        booking_frequency_limit: 'one pass per week',
      },
    });
    render(
      <CouponRow
        pass={pass}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={null}
        onBook={() => {}}
      />,
    );
    expect(screen.getByText(/Booking limit/)).toBeInTheDocument();
    expect(screen.getByText(/one pass per week/)).toBeInTheDocument();
  });

  it('handles null coupon without crashing', () => {
    render(
      <CouponRow
        pass={makePass({ coupon: null })}
        library={libWakefield}
        verdict={eligibleVerdict}
        distanceMi={null}
        onBook={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: /book/i })).toBeInTheDocument();
  });
});
