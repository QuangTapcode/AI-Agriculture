import { lazy, Suspense, useState } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes, useLocation } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingSpinner from './components/LoadingSpinner';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import { AuthProvider } from './contexts/AuthContext';
import { useLanguage } from './contexts/LanguageContext';

const AIChatPage = lazy(() => import('./pages/AIChatPage'));
const AlertManagementPage = lazy(() => import('./pages/AlertManagementPage'));
const AlertPage = lazy(() => import('./pages/AlertPage'));
const ArticlesPage = lazy(() => import('./pages/ArticlesPage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));
const CropDetailPage = lazy(() => import('./pages/CropDetailPage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const FeaturesPage = lazy(() => import('./pages/FeaturesPage'));
const ForecastPage = lazy(() => import('./pages/ForecastPage'));
const HarvestForecastPage = lazy(() => import('./pages/HarvestForecastPage'));
const HarvestPage = lazy(() => import('./pages/HarvestPage'));
const LandingPage = lazy(() => import('./pages/LandingPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const MarketPage = lazy(() => import('./pages/MarketPage'));
const MarketStrategyPage = lazy(() => import('./pages/MarketStrategyPage'));
const NewDashboard = lazy(() => import('./pages/NewDashboard'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const PricingDashboard = lazy(() => import('./pages/PricingDashboard'));
const PricingPage = lazy(() => import('./pages/PricingPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const QualityCheckPage = lazy(() => import('./pages/QualityCheckPage'));
const QualityPage = lazy(() => import('./pages/QualityPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const SeasonManagementPage = lazy(() => import('./pages/SeasonManagementPage'));
const SubscriptionPricingPage = lazy(() => import('./pages/SubscriptionPricingPage'));

const publicRoutes = new Set(['/', '/features', '/articles', '/pricing-plans', '/contact', '/login', '/register']);

const appRoutes = [
  '/dashboard',
  '/dashboard-new',
  '/pricing',
  '/pricing-dashboard',
  '/crop',
  '/quality',
  '/quality-check',
  '/harvest',
  '/harvest-forecast',
  '/weather',
  '/market',
  '/market-strategy',
  '/alerts',
  '/alerts-management',
  '/reports',
  '/ai-chat',
  '/notifications',
  '/season-management',
  '/settings',
  '/profile',
];

const localeSegments = new Set(['en', 'vi']);

const normalizePathname = (pathname) => {
  const segments = pathname.split('/').filter(Boolean);

  if (!segments.length || !localeSegments.has(segments[0])) {
    return pathname;
  }

  const normalizedPath = `/${segments.slice(1).join('/')}`;
  return normalizedPath === '/' ? normalizedPath : normalizedPath.replace(/\/$/, '') || '/';
};

const isKnownAppRoute = (pathname) =>
  appRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));

const publicRouteConfigs = [
  { path: '/', element: <LandingPage /> },
  { path: '/features', element: <FeaturesPage /> },
  { path: '/articles', element: <ArticlesPage /> },
  { path: '/pricing-plans', element: <SubscriptionPricingPage /> },
  { path: '/contact', element: <ContactPage /> },
  { path: '/login', element: <LoginPage initialMode="login" /> },
  { path: '/register', element: <LoginPage initialMode="register" /> },
];

const renderLocalizedRoutes = (routeConfigs) =>
  routeConfigs.flatMap(({ path, element }) => {
    const localizedPath = path === '/' ? '/:locale' : `/:locale${path}`;
    return [
      <Route key={path} path={path} element={element} />,
      <Route key={localizedPath} path={localizedPath} element={element} />,
    ];
  });

const PublicRoutes = () => <Routes>{renderLocalizedRoutes(publicRouteConfigs)}</Routes>;

const AppShell = ({ sidebarOpen, setSidebarOpen }) => {
  const { t } = useLanguage();

  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

        <div className="flex flex-1 flex-col lg:ml-64">
          <Navbar setSidebarOpen={setSidebarOpen} />

          <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
            <Suspense fallback={<LoadingSpinner text={t('loadingPage')} />}>
              <Routes>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/:locale/dashboard" element={<Dashboard />} />
                <Route path="/dashboard-new" element={<NewDashboard />} />
                <Route path="/:locale/dashboard-new" element={<NewDashboard />} />

                <Route path="/pricing" element={<PricingPage />} />
                <Route path="/:locale/pricing" element={<PricingPage />} />
                <Route path="/pricing-dashboard" element={<PricingDashboard />} />
                <Route path="/:locale/pricing-dashboard" element={<PricingDashboard />} />
                <Route path="/crop/:cropId" element={<CropDetailPage />} />
                <Route path="/:locale/crop/:cropId" element={<CropDetailPage />} />

                <Route path="/quality" element={<QualityPage />} />
                <Route path="/:locale/quality" element={<QualityPage />} />
                <Route path="/quality-check" element={<QualityCheckPage />} />
                <Route path="/:locale/quality-check" element={<QualityCheckPage />} />

                <Route path="/harvest" element={<HarvestPage />} />
                <Route path="/:locale/harvest" element={<HarvestPage />} />
                <Route path="/harvest-forecast" element={<HarvestForecastPage />} />
                <Route path="/:locale/harvest-forecast" element={<HarvestForecastPage />} />
                <Route path="/weather" element={<ForecastPage />} />
                <Route path="/:locale/weather" element={<ForecastPage />} />

                <Route path="/market" element={<MarketPage />} />
                <Route path="/:locale/market" element={<MarketPage />} />
                <Route path="/market-strategy" element={<MarketStrategyPage />} />
                <Route path="/:locale/market-strategy" element={<MarketStrategyPage />} />

                <Route path="/alerts" element={<AlertPage />} />
                <Route path="/:locale/alerts" element={<AlertPage />} />
                <Route path="/alerts-management" element={<AlertManagementPage />} />
                <Route path="/:locale/alerts-management" element={<AlertManagementPage />} />

                <Route path="/ai-chat/*" element={<AIChatPage />} />
                <Route path="/:locale/ai-chat/*" element={<AIChatPage />} />
                <Route path="/notifications" element={<NotificationsPage />} />
                <Route path="/:locale/notifications" element={<NotificationsPage />} />
                <Route path="/season-management" element={<SeasonManagementPage />} />
                <Route path="/:locale/season-management" element={<SeasonManagementPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/:locale/settings" element={<SettingsPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/:locale/profile" element={<ProfilePage />} />
                <Route path="*" element={<NotFoundPage publicLayout={false} />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
};

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { t } = useLanguage();

  const pageFallback = (
    <div className="min-h-screen bg-gray-50">
      <LoadingSpinner text={t('loadingInterface')} />
    </div>
  );

  const normalizedPathname =
    location.pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, '') || '/';

  if (publicRoutes.has(normalizedPathname)) {
    return (
      <Suspense fallback={pageFallback}>
        <PublicRoutes />
      </Suspense>
    );
  }

  if (!isKnownAppRoute(normalizedPathname)) {
    return (
      <Suspense fallback={pageFallback}>
        <NotFoundPage />
      </Suspense>
    );
  }

  return <AppShell sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />;
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <AppContent />
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
