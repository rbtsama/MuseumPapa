import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PickupBranches } from './PickupBranches';

describe('PickupBranches', () => {
  it('renders nothing for a single-branch (or branchless) library', () => {
    // Assabet libraries have no branch list — should collapse to null.
    const { container } = render(<PickupBranches libraryId="wakefield" userGeo={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows branch count and nearest-with-distance when a home geo is known', () => {
    // Home near downtown Boston → nearest BPL branch reported with a mileage.
    render(<PickupBranches libraryId="bpl" userGeo={{ lat: 42.36, lon: -71.06 }} />);
    const btn = screen.getByRole('button');
    expect(btn.textContent).toMatch(/24 branches · nearest .+ \([\d.]+ mi\)/);
  });

  it('expands into a distance-sorted list, nearest first', () => {
    render(<PickupBranches libraryId="bpl" userGeo={{ lat: 42.36, lon: -71.06 }} />);
    fireEvent.click(screen.getByRole('button'));
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(24);
    // Distances are non-decreasing down the list.
    const miles = items.map(li => {
      const m = li.textContent?.match(/([\d.]+) mi/);
      return m ? parseFloat(m[1]) : NaN;
    });
    for (let i = 1; i < miles.length; i++) expect(miles[i]).toBeGreaterThanOrEqual(miles[i - 1]);
  });

  it('falls back to a count-only summary when home geo is unknown', () => {
    render(<PickupBranches libraryId="bpl" userGeo={null} />);
    expect(screen.getByRole('button').textContent).toMatch(/Pick up at any of 24 branches/);
  });
});
