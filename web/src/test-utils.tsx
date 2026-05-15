import { render } from '@testing-library/react';
import { HeroUIProvider } from '@heroui/react';
import { MemoryRouter } from 'react-router';
import type React from 'react';

export function renderApp(ui: React.ReactElement, opts: { route?: string } = {}) {
  const route = opts.route ?? '/';
  return render(
    <HeroUIProvider>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </HeroUIProvider>
  );
}
