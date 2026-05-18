import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PassDeliveryChip } from './PassDeliveryChip';

describe('PassDeliveryChip', () => {
  it('renders Email chip for digital pass without distance', () => {
    render(<PassDeliveryChip passType="digital" distanceMi={42} />);
    const chip = screen.getByText(/Email/);
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).not.toMatch(/mi/);
  });

  it('renders Pickup chip with rounded distance', () => {
    render(<PassDeliveryChip passType="physical-coupon" distanceMi={6.7} />);
    expect(screen.getByText(/Pickup 7mi/)).toBeInTheDocument();
  });

  it('renders Borrow chip with rounded distance', () => {
    render(<PassDeliveryChip passType="physical-circ" distanceMi={12.3} />);
    expect(screen.getByText(/Borrow 12mi/)).toBeInTheDocument();
  });

  it('omits distance for physical pass when distanceMi is null', () => {
    render(<PassDeliveryChip passType="physical-coupon" distanceMi={null} />);
    const chip = screen.getByText(/Pickup/);
    expect(chip.textContent).not.toMatch(/mi/);
  });
});
