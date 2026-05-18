import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DescriptionBlock } from './DescriptionBlock';

describe('DescriptionBlock', () => {
  it('renders nothing when description is null', () => {
    const { container } = render(<DescriptionBlock description={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders short description without Read more', () => {
    render(<DescriptionBlock description="Short blurb about the museum." />);
    expect(screen.getByText(/Short blurb/)).toBeInTheDocument();
    expect(screen.queryByText(/Read more/i)).not.toBeInTheDocument();
  });

  it('shows Read more for long description and expands on click', () => {
    const long = 'X'.repeat(250);
    render(<DescriptionBlock description={long} />);
    const btn = screen.getByText(/Read more/i);
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.queryByText(/Read more/i)).not.toBeInTheDocument();
  });
});
