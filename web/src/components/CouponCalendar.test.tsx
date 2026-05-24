/**
 * CouponCalendar.test.tsx
 *
 * Pure presentational component — test directly with prop injection.
 * We use a fixed todayIso set to the FIRST day of the test month so that
 * all mid-month dates are in the future and `isPast` never fires.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CouponCalendar } from './CouponCalendar';

// Fixed test month and today so we control isPast logic.
const MONTH = '2030-06';
const TODAY_ISO = '2030-06-01'; // today = first of month; mid-month dates are NOT past

const BASE_CELL_INFO = {
  // available date: mid-month, not past
  '2030-06-15': { best: 'FREE', isFree: true, status: 'available' as const },
  // booked date
  '2030-06-16': { best: '', isFree: false, status: 'booked' as const },
  // closed date
  '2030-06-17': { best: '', isFree: false, status: 'closed' as const },
  // none / no info
  '2030-06-18': { best: '', isFree: false, status: 'none' as const },
};

describe('CouponCalendar', () => {
  it('renders an available date with the coupon label and a clickable button', () => {
    const onSelect = vi.fn();
    render(
      <CouponCalendar
        month={MONTH}
        selectedDate={null}
        todayIso={TODAY_ISO}
        cellInfo={BASE_CELL_INFO}
        onSelect={onSelect}
      />
    );

    // The 15th should render and have FREE label visible.
    // Find all buttons, locate the one for day 15.
    const buttons = screen.getAllByRole('button');
    const day15 = buttons.find(b => b.getAttribute('data-status') === 'available');
    expect(day15).toBeDefined();
    expect(day15).not.toBeDisabled();
    expect(day15).toHaveTextContent('FREE');

    // Clicking an available date calls onSelect.
    fireEvent.click(day15!);
    expect(onSelect).toHaveBeenCalledWith('2030-06-15');
  });

  it('renders a booked date with a disabled button that does NOT call onSelect on click', () => {
    const onSelect = vi.fn();
    render(
      <CouponCalendar
        month={MONTH}
        selectedDate={null}
        todayIso={TODAY_ISO}
        cellInfo={BASE_CELL_INFO}
        onSelect={onSelect}
      />
    );

    const buttons = screen.getAllByRole('button');
    const day16 = buttons.find(b => b.getAttribute('data-status') === 'booked');
    expect(day16).toBeDefined();
    // The button must be disabled.
    expect(day16).toBeDisabled();

    // Clicking a disabled button should NOT call onSelect.
    fireEvent.click(day16!);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('renders a closed date with line-through on the day number and a disabled button', () => {
    const onSelect = vi.fn();
    render(
      <CouponCalendar
        month={MONTH}
        selectedDate={null}
        todayIso={TODAY_ISO}
        cellInfo={BASE_CELL_INFO}
        onSelect={onSelect}
      />
    );

    const buttons = screen.getAllByRole('button');
    const day17 = buttons.find(b => b.getAttribute('data-status') === 'closed');
    expect(day17).toBeDefined();
    // Must be disabled.
    expect(day17).toBeDisabled();

    // The day-number span should have line-through text-decoration.
    // It is the first <span> child inside the button.
    const daySpan = day17!.querySelector('span:first-child') as HTMLElement;
    expect(daySpan).toBeDefined();
    expect(daySpan.style.textDecoration).toBe('line-through');

    // Clicking a disabled button should NOT call onSelect.
    fireEvent.click(day17!);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('renders a none-status date with a clickable button (neutral default)', () => {
    const onSelect = vi.fn();
    render(
      <CouponCalendar
        month={MONTH}
        selectedDate={null}
        todayIso={TODAY_ISO}
        cellInfo={BASE_CELL_INFO}
        onSelect={onSelect}
      />
    );

    // Find specifically the button for day 18 (none-status, not past).
    // Buttons are rendered in calendar order; find by data-status='none' AND containing '18'.
    const buttons = screen.getAllByRole('button');
    // day 18 has status:'none' explicitly set in cellInfo — pick the button that
    // has data-status='none' and whose text includes '18'.
    const day18 = buttons.find(
      b => b.getAttribute('data-status') === 'none' && b.textContent?.includes('18')
    );
    expect(day18).toBeDefined();
    // 'none' status → still clickable (user can select to see "no coupons").
    expect(day18).not.toBeDisabled();

    fireEvent.click(day18!);
    expect(onSelect).toHaveBeenCalledWith('2030-06-18');
  });
});
