import { Bell, HelpCircle, LogOut, Menu, Settings, User } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { navigation } from './Sidebar';

const iconButtonClass =
  'flex min-h-11 min-w-11 items-center justify-center rounded-xl text-[#A7BCB0] transition-colors duration-200 hover:bg-white/[0.08] hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime motion-reduce:transition-none';

const stripLocale = (pathname) => pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, '') || '/';

const Navbar = ({ setSidebarOpen }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user, isAuthenticated } = useAuth();
  const { language, t } = useLanguage();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const currentPath = stripLocale(location.pathname);

  const currentPage = navigation.find((item) =>
    item.match.some((path) => currentPath === path || currentPath.startsWith(`${path}/`))
  );

  const pageTitle = currentPage ? currentPage.name[language] : 'AgriAI';
  const PageIcon = currentPage?.icon;

  return (
    <header className="sticky top-0 z-10 border-b border-white/10 bg-field-ink">
      <div className="flex h-16 items-center justify-between gap-3 px-3 md:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className={`${iconButtonClass} lg:hidden`}
            aria-label={t('openMenu')}
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
          <div className="flex min-w-0 items-center gap-2.5">
            {PageIcon && <PageIcon className="hidden h-5 w-5 shrink-0 text-field-lime sm:block" aria-hidden="true" />}
            {/* Trang nội dung đã có <h1> riêng; thanh trên chỉ là nhãn ngữ cảnh. */}
            <p className="truncate font-display text-base font-extrabold tracking-tight text-white md:text-lg">
              {pageTitle}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-0.5 md:gap-1">
          <Link to="/notifications" className={iconButtonClass} aria-label={t('viewNotifications')}>
            <Bell className="h-5 w-5" aria-hidden="true" />
          </Link>
          <Link to="/contact" className={`${iconButtonClass} hidden sm:flex`} aria-label={t('help')}>
            <HelpCircle className="h-5 w-5" aria-hidden="true" />
          </Link>
          <Link to="/settings" className={`${iconButtonClass} hidden sm:flex`} aria-label={t('settings')}>
            <Settings className="h-5 w-5" aria-hidden="true" />
          </Link>

          {isAuthenticated ? (
            <>
              <Link
                to="/profile"
                className="ml-1 flex min-h-11 items-center gap-2 rounded-full py-1 pl-1 pr-1 transition-colors duration-200 hover:bg-white/[0.08] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime motion-reduce:transition-none xl:pr-3"
                aria-label={t('profile')}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-field-lime">
                  <User className="h-[1.125rem] w-[1.125rem] text-field-ink" aria-hidden="true" />
                </span>
                <span className="hidden max-w-36 truncate text-sm font-semibold text-white xl:block">
                  {user?.name || t('account')}
                </span>
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className={iconButtonClass}
                aria-label={t('logout')}
              >
                <LogOut className="h-5 w-5" aria-hidden="true" />
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="flex min-h-11 items-center rounded-full px-4 text-sm font-bold text-field-lime transition-colors duration-200 hover:bg-field-lime/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime motion-reduce:transition-none"
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
