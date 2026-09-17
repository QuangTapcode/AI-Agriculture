import { describe, expect, it } from 'vitest';
import { resolveRoute } from '../appRoutes';

describe('route resolution', () => {
  it('treats /reports as a real app route instead of a not-found page', () => {
    expect(resolveRoute('/reports')).toMatchObject({ kind: 'app', path: '/reports' });
  });

  it.each([
    ['/dashboard-new', '/dashboard'],
    ['/pricing-dashboard', '/pricing'],
    ['/quality-check', '/quality'],
    ['/harvest', '/season-management'],
    ['/harvest-forecast', '/season-management'],
    ['/market', '/dashboard'],
    ['/market-strategy', '/dashboard'],
    ['/alerts-management', '/alerts'],
  ])('redirects the retired route %s to %s', (legacy, canonical) => {
    expect(resolveRoute(legacy)).toMatchObject({ kind: 'redirect', to: canonical });
  });
});

describe('locale prefixes', () => {
  it('keeps the locale segment when redirecting a retired route', () => {
    expect(resolveRoute('/en/harvest-forecast')).toMatchObject({ kind: 'redirect', to: '/en/season-management' });
  });

  it('resolves a localized app route to the same app page', () => {
    expect(resolveRoute('/en/reports')).toMatchObject({ kind: 'app', path: '/reports' });
  });
});

describe('public routes', () => {
  it('classifies the marketing and auth pages as public', () => {
    expect(resolveRoute('/')).toMatchObject({ kind: 'public', path: '/' });
    expect(resolveRoute('/contact')).toMatchObject({ kind: 'public', path: '/contact' });
    expect(resolveRoute('/en/login')).toMatchObject({ kind: 'public', path: '/login' });
  });
});

describe('nested app routes', () => {
  it('resolves detail and conversation sub-paths to the app shell', () => {
    expect(resolveRoute('/crop/robusta')).toMatchObject({ kind: 'app' });
    expect(resolveRoute('/ai-chat/2024-06-01')).toMatchObject({ kind: 'app' });
  });

  it('does not expose removed forecast or market analysis pages as app routes', () => {
    expect(resolveRoute('/market')).toMatchObject({ kind: 'redirect', to: '/dashboard' });
    expect(resolveRoute('/harvest')).toMatchObject({ kind: 'redirect', to: '/season-management' });
  });

  it('still rejects an unknown path', () => {
    expect(resolveRoute('/khong-ton-tai')).toMatchObject({ kind: 'notFound' });
  });
});
