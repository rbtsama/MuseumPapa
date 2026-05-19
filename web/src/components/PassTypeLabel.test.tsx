import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from '../test-utils';
import { PassTypeLabel } from './PassTypeLabel';

describe('PassTypeLabel', () => {
  it('renders "Email" for digital type', () => {
    renderApp(<PassTypeLabel type="digital" />);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('renders "Pickup" for physical-coupon type', () => {
    renderApp(<PassTypeLabel type="physical-coupon" />);
    expect(screen.getByText('Pickup')).toBeInTheDocument();
  });

  it('renders "Pik&Rtn" for physical-circ type (the value the data layer actually emits)', () => {
    renderApp(<PassTypeLabel type="physical-circ" />);
    expect(screen.getByText('Pik&Rtn')).toBeInTheDocument();
  });

  it('renders "Pass" for unknown type', () => {
    renderApp(<PassTypeLabel type="unknown" />);
    expect(screen.getByText('Pass')).toBeInTheDocument();
  });
});
