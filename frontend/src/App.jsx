import { lazy, Suspense, useState } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes, useLocation } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingSpinner from './components/LoadingSpinner';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import { AuthProvider } from './contexts/AuthContext';
import { useLanguage } from './contexts/LanguageContext';
import { resolveRoute } from './routes/appRoutes';

const AIChatPage = lazy(() => import('./pages/AIChatPage'));
const AlertPage = lazy(() => import('./pages/AlertPage'));
const ArticlesPage = lazy(() => import('./pages/ArticlesPage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));
const CropDetailPage = lazy(() => import('./pages/CropDetailPage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const FeaturesPage = lazy(() => import('./pages/FeaturesPage'));
const ForecastPage = lazy(() => import('./pages/ForecastPage'));
const HarvestPage = lazy(() => import('./pages/HarvestPage'));
const KnowledgeDocumentsPage = lazy(() => import('./pages/KnowledgeDocumentsPage'));
const LandingPage = lazy(() => import('./pages/LandingPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const MarketPage = lazy(() => import('./pages/MarketPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const PricingPage = lazy(() => import('./pages/PricingPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const QualityPage = lazy(() => import('./pages/QualityPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const SeasonManagementPage = lazy(() => import('./pages/SeasonManagementPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const SubscriptionPricingPage = lazy(() => import('./pages/SubscriptionPricingPage'));

const publicRouteConfigs = [
  { path: '/', element: <LandingPage /> },
  { path: '/features', element: <FeaturesPage /> },
  { path: '/articles', element: <ArticlesPage /> },
  { path: '/pricing-plans', element: <SubscriptionPricingPage /> },
  { path: '/contact', element: <ContactPage /> },
  { path: '/login', element: <LoginPage initialMode="login" /> },
  { path: '/register', element: <LoginPage initialMode="register" /> },
];

const appRouteConfigs = [
  { path: '/dashboard', element: <Dashboard /> },
  { path: '/reports', element: <ReportsPage /> },
  { path: '/weather', element: <ForecastPage /> },
  { path: '/pricing', element: <PricingPage /> },
  { path: '/crop/:cropId', element: <CropDetailPage /> },
  { path: '/market', element: <MarketPage /> },
  { path: '/quality', element: <QualityPage /> },
  { path: '/harvest', element: <HarvestPage /> },
  { path: '/season-management', element: <SeasonManagementPage /> },
  { path: '/alerts', element: <AlertPage /> },
  { path: '/notifications', element: <NotificationsPage /> },
  { path: '/ai-chat/*', element: <AIChatPage /> },
  { path: '/knowledge-documents', element: <KnowledgeDocumentsPage /> },
  { path: '/settings', element: <SettingsPage /> },
  { path: '/profile', element: <ProfilePage /> },
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
      <div className="flex min-h-screen bg-field-canvas">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-field-lime focus:px-5 focus:py-3 focus:text-sm focus:font-bold focus:text-field-ink"
        >
          Bỏ qua điều hướng, tới nội dung chính
        </a>
        <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

        <div className="flex min-w-0 flex-1 flex-col lg:ml-64">
          <Navbar setSidebarOpen={setSidebarOpen} />

          <main
            id="main-content"
            className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-4 md:p-6 lg:p-8"
          >
            <Suspense fallback={<LoadingSpinner text={t('loadingPage')} />}>
              <Routes>
                {renderLocalizedRoutes(appRouteConfigs)}
                <Route path="*" element={<NotFoundPage publicLayout={false} />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  );
};

export function AppRoutes() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { t } = useLanguage();

  const pageFallback = (
    <div className="min-h-screen bg-field-canvas">
      <LoadingSpinner text={t('loadingInterface')} />
    </div>
  );

  const route = resolveRoute(location.pathname);

  if (route.kind === 'redirect') {
    return <Navigate to={`${route.to}${location.search}${location.hash}`} replace />;
  }

  if (route.kind === 'public') {
    return (
      <Suspense fallback={pageFallback}>
        <PublicRoutes />
      </Suspense>
    );
  }

  if (route.kind === 'notFound') {
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
          <AppRoutes />
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
