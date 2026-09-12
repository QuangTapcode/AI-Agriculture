import { describe, expect, it } from 'vitest';
import { resolveRoute } from '../../routes/appRoutes';

describe('legacy route redirects', () => {
  it.each([
    ['/dashboard-new', '/dashboard'],
    ['/pricing-dashboard', '/pricing'],
    ['/quality-check', '/quality'],
    ['/harvest-forecast', '/harvest'],
    ['/market-strategy', '/market'],
    ['/alerts-management', '/alerts'],
  ])('maps %s to %s', (legacy, canonical) => {
    expect(resolveRoute(legacy)).toMatchObject({ kind: 'redirect', to: canonical });
  });

  it('preserves the locale prefix', () => {
    expect(resolveRoute('/en/quality-check')).toMatchObject({ kind: 'redirect', to: '/en/quality' });
    expect(resolveRoute('/vi/dashboard-new')).toMatchObject({ kind: 'redirect', to: '/vi/dashboard' });
  });

  it('does not redirect a canonical route', () => {
    expect(resolveRoute('/reports')).toMatchObject({ kind: 'app', path: '/reports' });
  });
});
