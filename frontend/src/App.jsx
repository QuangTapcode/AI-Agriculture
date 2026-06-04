import { lazy, Suspense, useState } from 'react';
import { Route, BrowserRouter as Router, Routes, useLocation } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import LoadingSpinner from './components/LoadingSpinner';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import { AuthProvider } from './contexts/AuthContext';

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

const pageFallback = (
  <div className="min-h-screen bg-gray-50">
    <LoadingSpinner text="Đang tải giao diện..." />
  </div>
);

const publicRoutes = new Set([
  '/',
  '/features',
  '/articles',
  '/pricing-plans',
  '/contact',
  '/login',
  '/register',
]);

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

const isKnownAppRoute = (pathname) =>
  appRoutes.some((route) => pathname === route || pathname.startsWith(`${route}/`));

const PublicRoutes = () => (
  <Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/features" element={<FeaturesPage />} />
    <Route path="/articles" element={<ArticlesPage />} />
    <Route path="/pricing-plans" element={<SubscriptionPricingPage />} />
    <Route path="/contact" element={<ContactPage />} />
    <Route path="/login" element={<LoginPage initialMode="login" />} />
    <Route path="/register" element={<LoginPage initialMode="register" />} />
  </Routes>
);

const AppShell = ({ sidebarOpen, setSidebarOpen }) => (
  <ProtectedRoute>
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />

      <div className="flex flex-1 flex-col lg:ml-64">
        <Navbar setSidebarOpen={setSidebarOpen} />

        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          <Suspense fallback={<LoadingSpinner text="Đang tải trang..." />}>
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/dashboard-new" element={<NewDashboard />} />

              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/pricing-dashboard" element={<PricingDashboard />} />
              <Route path="/crop/:cropId" element={<CropDetailPage />} />

              <Route path="/quality" element={<QualityPage />} />
              <Route path="/quality-check" element={<QualityCheckPage />} />

              <Route path="/harvest" element={<HarvestPage />} />
              <Route path="/harvest-forecast" element={<HarvestForecastPage />} />
              <Route path="/weather" element={<ForecastPage />} />

              <Route path="/market" element={<MarketPage />} />
              <Route path="/market-strategy" element={<MarketStrategyPage />} />

              <Route path="/alerts" element={<AlertPage />} />
              <Route path="/alerts-management" element={<AlertManagementPage />} />

              <Route path="/ai-chat" element={<AIChatPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/season-management" element={<SeasonManagementPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="*" element={<NotFoundPage publicLayout={false} />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  </ProtectedRoute>
);

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  if (publicRoutes.has(location.pathname)) {
    return (
      <Suspense fallback={pageFallback}>
        <PublicRoutes />
      </Suspense>
    );
  }

  if (!isKnownAppRoute(location.pathname)) {
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
