export const PUBLIC_ROUTES = [
  '/',
  '/features',
  '/articles',
  '/pricing-plans',
  '/contact',
  '/login',
  '/register',
];

export const APP_ROUTES = [
  '/dashboard',
  '/reports',
  '/weather',
  '/pricing',
  '/crop',
  '/market',
  '/quality',
  '/harvest',
  '/season-management',
  '/alerts',
  '/notifications',
  '/ai-chat',
  '/knowledge-documents',
  '/settings',
  '/profile',
];

export const LEGACY_ROUTE_REDIRECTS = {
  '/dashboard-new': '/dashboard',
  '/pricing-dashboard': '/pricing',
  '/quality-check': '/quality',
  '/harvest-forecast': '/harvest',
  '/market-strategy': '/market',
  '/alerts-management': '/alerts',
};

const LOCALE_SEGMENTS = new Set(['en', 'vi']);

function splitLocale(pathname) {
  const segments = String(pathname || '/').split('/').filter(Boolean);

  if (segments.length && LOCALE_SEGMENTS.has(segments[0].toLowerCase())) {
    const locale = segments[0].toLowerCase();
    const rest = `/${segments.slice(1).join('/')}`;
    return { locale, path: rest === '/' ? '/' : rest };
  }

  return { locale: null, path: segments.length ? `/${segments.join('/')}` : '/' };
}

const withLocale = (locale, path) => (locale ? `/${locale}${path === '/' ? '' : path}` || '/' : path);

export function resolveRoute(pathname) {
  const { locale, path } = splitLocale(pathname);

  const redirectTo = LEGACY_ROUTE_REDIRECTS[path];
  if (redirectTo) {
    return { kind: 'redirect', to: withLocale(locale, redirectTo), path, locale };
  }

  if (PUBLIC_ROUTES.includes(path)) {
    return { kind: 'public', path, locale };
  }

  const appRoute = APP_ROUTES.find((route) => path === route || path.startsWith(`${route}/`));
  if (appRoute) {
    return { kind: 'app', path, locale };
  }

  return { kind: 'notFound', path, locale };
}
