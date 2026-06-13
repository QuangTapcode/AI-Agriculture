import { Bell, HelpCircle, LogOut, Menu, Settings, User } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { navigation } from './Sidebar';

const Navbar = ({ setSidebarOpen }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user, isAuthenticated } = useAuth();
  const { language, t } = useLanguage();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const currentPage = navigation.find((item) =>
    item.match.some((path) =>
      path === item.href ? location.pathname === path : location.pathname.startsWith(path)
    )
  );

  const pageTitle = currentPage ? currentPage.name[language] : 'AgriAI';
  const PageIcon = currentPage?.icon;

  return (
    <header className="sticky top-0 z-10 border-b border-gray-200 bg-white">
      <div className="flex h-16 items-center justify-between px-4 md:px-6">
        <div className="flex flex-1 items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 lg:hidden"
            aria-label={t('openMenu')}
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex items-center gap-2">
            {PageIcon && <PageIcon className="h-5 w-5 text-emerald-600" />}
            <h1 className="text-lg font-bold text-gray-900">{pageTitle}</h1>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          <Link
            to="/notifications"
            className="relative rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label={t('viewNotifications')}
            title={t('notifications')}
          >
            <Bell className="h-5 w-5" />
            <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-green-600" />
          </Link>
          <Link
            to="/contact"
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label={t('help')}
            title={t('help')}
          >
            <HelpCircle className="h-5 w-5" />
          </Link>
          <Link
            to="/settings"
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            aria-label={t('settings')}
            title={t('settings')}
          >
            <Settings className="h-5 w-5" />
          </Link>
          {isAuthenticated ? (
            <>
              <Link
                to="/profile"
                className="hidden items-center gap-2 rounded-lg p-2 hover:bg-gray-100 sm:flex"
                aria-label={t('profile')}
                title={t('profile')}
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600">
                  <User className="h-5 w-5 text-white" />
                </span>
                <span className="hidden max-w-32 truncate text-sm font-medium text-gray-700 xl:block">
                  {user?.name || t('account')}
                </span>
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-red-600"
                aria-label={t('logout')}
                title={t('logout')}
              >
                <LogOut className="h-5 w-5" />
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              aria-label={t('login')}
              title={t('login')}
            >
              {t('login')}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};

export default Navbar;
