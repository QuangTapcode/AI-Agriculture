import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { PageTransition } from '../PageTransition';

describe('PageTransition', () => {
  it('keeps page content mounted in a transition wrapper', () => {
    render(<MemoryRouter><PageTransition pageKey="/dashboard"><h1>Dashboard</h1></PageTransition></MemoryRouter>);
    const content = screen.getByRole('heading', { name: 'Dashboard' });
    expect(content.parentElement).toHaveAttribute('data-page-transition', '/dashboard');
    expect(content.parentElement).toHaveClass('field-page-transition');
  });
});
