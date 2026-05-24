import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { PassTypeLabel } from './PassTypeLabel';

describe('PassTypeLabel', () => {
  it('renders "Email" for digital_email form', () => {
    renderApp(<PassTypeLabel type="digital_email" />);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('renders "Coupon" for physical_coupon form', () => {
    renderApp(<PassTypeLabel type="physical_coupon" />);
    expect(screen.getByText('Coupon')).toBeInTheDocument();
  });

  it('renders "Pickup" for physical_circ form (the value the data layer actually emits)', () => {
    renderApp(<PassTypeLabel type="physical_circ" />);
    expect(screen.getByText('Pickup')).toBeInTheDocument();
  });
});
