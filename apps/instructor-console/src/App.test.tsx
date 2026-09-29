import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App routing', () => {
  it('shows the honest placeholder for planned pages, with header and footer', () => {
    renderAt('/fleet');
    expect(screen.getByRole('heading', { name: 'Fleet' })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent(
      'Planned — Phase 5 (see docs/10_ROADMAP.md)',
    );
    expect(screen.getByAltText('Chakravyuha Dynamics logo placeholder')).toBeInTheDocument();
    expect(screen.getByText('CDPL proprietary · Phase 0 skeleton')).toBeInTheDocument();
  });

  it('renders the platforms table from the API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: 'quad_x',
              name: 'Quad X',
              class: 'multirotor',
              status: 'draft',
              version: '0.1.0',
            },
          ]),
          { status: 200 },
        ),
      ),
    );
    renderAt('/platforms');
    expect(await screen.findByText('Quad X')).toBeInTheDocument();
    expect(screen.getByText('multirotor')).toBeInTheDocument();
  });
});
