import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RestrictionsBadge } from './RestrictionsBadge';

describe('RestrictionsBadge', () => {
  it('renders nothing when restrictions are null', () => {
    const { container } = render(<RestrictionsBadge restrictions={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the ⚠ glyph with a summarized tooltip when any flag is set', () => {
    render(<RestrictionsBadge restrictions={{
      blackout_dates: true, weekdays_only: true, seasonal: null, reservation_required: false,
    }} />);
    const node = screen.getByText('⚠');
    expect(node.getAttribute('title')).toMatch(/blackout/);
    expect(node.getAttribute('title')).toMatch(/weekdays only/);
  });

  it('includes the seasonal window in the tooltip', () => {
    render(<RestrictionsBadge restrictions={{
      blackout_dates: false, weekdays_only: false, seasonal: 'May–Oct', reservation_required: true,
    }} />);
    const node = screen.getByText('⚠');
    expect(node.getAttribute('title')).toMatch(/May/);
    expect(node.getAttribute('title')).toMatch(/reservation/);
  });

  it('renders nothing when restrictions object exists but every flag is empty', () => {
    const { container } = render(<RestrictionsBadge restrictions={{
      blackout_dates: false, weekdays_only: false, seasonal: null, reservation_required: false,
    }} />);
    expect(container.firstChild).toBeNull();
  });
});
