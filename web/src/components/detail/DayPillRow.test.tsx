import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DayPillRow } from './DayPillRow';

describe('DayPillRow', () => {
  const baseProps = {
    todayIso: '2026-05-18',
    selectedDate: '2026-05-18',
    month: '2026-05',
    setMonth: vi.fn(),
    cellInfo: {},
    monthPills: ['2026-05'],
  };

  it('renders 7 day pills + a pick pill', () => {
    render(<DayPillRow {...baseProps} onSelect={() => {}} />);
    expect(screen.getByText(/TODAY/)).toBeInTheDocument();
    expect(screen.getByText(/📅/)).toBeInTheDocument();
  });

  it('calls onSelect when a day pill is clicked', () => {
    const onSelect = vi.fn();
    render(<DayPillRow {...baseProps} onSelect={onSelect} />);
    const pills = screen.getAllByRole('button');
    fireEvent.click(pills[1]); // second pill = tomorrow
    expect(onSelect).toHaveBeenCalled();
  });

  it('toggles calendar expander when pick pill clicked', () => {
    render(<DayPillRow {...baseProps} onSelect={() => {}} />);
    expect(screen.queryAllByText(/May 2026/).length).toBe(0);
    fireEvent.click(screen.getByText(/📅/));
    expect(screen.queryAllByText(/May 2026/).length).toBeGreaterThanOrEqual(1);
  });
});
