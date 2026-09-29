import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Header } from './Header';

describe('Header', () => {
  it('renders the Chakravyuha Dynamics logo placeholder and product name', () => {
    render(<Header />);
    expect(screen.getByAltText('Chakravyuha Dynamics logo placeholder')).toBeInTheDocument();
    expect(screen.getByText('Chakravyuha Dynamics')).toBeInTheDocument();
    expect(screen.getByText('CD Sim — Instructor Console')).toBeInTheDocument();
  });
});
