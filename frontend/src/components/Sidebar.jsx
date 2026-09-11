import {
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  CalendarDays,
  Camera,
  CloudSun,
  FileText,
  LayoutDashboard,
  Settings,
  Sprout,
  TrendingUp,
  X,
} from 'lucide-react';
import { useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import logo from '../assets/agri-ai-logo.png';
import { useLanguage } from '../contexts/LanguageContext';

export const navigation = [
  {
    key: 'weather',
    name: { vi: 'Thời tiết nông vụ', en: 'Crop Weather' },
    href: '/weather',
    icon: CloudSun,
    match: ['/weather'],
  },
  {
    key: 'dashboard',
    name: { vi: 'Bảng điều khiển', en: 'Dashboard' },
    href: '/dashboard',
    icon: LayoutDashboard,
    match: ['/dashboard'],
  },
  {
    key: 'reports',
    name: { vi: 'Báo cáo', en: 'Reports' },
    href: '/reports',
    icon: FileText,
    match: ['/reports'],
  },
  {
    key: 'pricing',
    name: { vi: 'Định giá nông sản', en: 'Crop Pricing' },
    href: '/pricing',
    icon: TrendingUp,
    match: ['/pricing', '/crop'],
  },
  {
    key: 'quality',
    name: { vi: 'Kiểm định chất lượng', en: 'Quality Check' },
    href: '/quality',
    icon: Camera,
    match: ['/quality'],
  },
  {
    key: 'harvest',
    name: { vi: 'Dự báo thu hoạch', en: 'Harvest Forecast' },
    href: '/harvest',
    icon: Sprout,
    match: ['/harvest'],
  },
  {
    key: 'seasonManagement',
    name: { vi: 'Quản lý mùa vụ', en: 'Season Management' },
    href: '/season-management',
    icon: CalendarDays,
    match: ['/season-management'],
  },
  {
    key: 'market',
    name: { vi: 'Phân tích thị trường', en: 'Market Analysis' },
    href: '/market',
    icon: BarChart3,
    match: ['/market'],
  },
  {
    key: 'alerts',
    name: { vi: 'Cảnh báo giá', en: 'Price Alerts' },
    href: '/alerts',
    icon: Bell,
    match: ['/alerts'],
  },
  {
    key: 'aiAssistant',
    name: { vi: 'Trợ lý AI', en: 'AI Assistant' },
    href: '/ai-chat',
    icon: Bot,
    match: ['/ai-chat'],
  },
  {
    key: 'knowledgeDocuments',
    name: { vi: 'Kho tài liệu', en: 'Knowledge Library' },
    href: '/knowledge-documents',
    icon: BookOpen,
    match: ['/knowledge-documents'],
  },
  {
    key: 'notifications',
    name: { vi: 'Thông báo', en: 'Notifications' },
    href: '/notifications',
    icon: Bell,
    match: ['/notifications'],
  },
  {
    key: 'settings',
    name: { vi: 'Cài đặt', en: 'Settings' },
    href: '/settings',
    icon: Settings,
    match: ['/settings'],
  },
];

const stripLocale = (pathname) => pathname.replace(/^\/[a-z]{2}(?=\/|$)/i, '') || '/';

const Sidebar = ({ open, setOpen }) => {
  const location = useLocation();
  const { language, t } = useLanguage();
  const closeButtonRef = useRef(null);

  const currentPath = stripLocale(location.pathname);

  const isActive = (item) =>
    item.match.some((path) => currentPath === path || currentPath.startsWith(`${path}/`));

  useEffect(() => {
    if (!open) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    closeButtonRef.current?.focus();

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, setOpen]);

  const linkClass = (active) =>
    [
      'group relative flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm',
      'transition-colors duration-200 motion-reduce:transition-none',
      'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime',
      active
        ? 'bg-field-lime/10 font-semibold text-field-lime'
        : 'font-medium text-[#A7BCB0] hover:bg-white/[0.06] hover:text-white',
    ].join(' ');

  return (
    <>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-field-ink/70 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
          aria-label={t('closeMenu')}
        />
      )}

      <aside
        aria-label={t('smartAgriculture')}
        className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-white/10 bg-field-ink transition-transform duration-300 ease-out motion-reduce:transition-none lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 shrink-0 items-center justify-between border-b border-white/10 px-5">
            <Link
              to="/"
              className="flex min-w-0 items-center gap-2.5 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-field-lime"
              onClick={() => setOpen(false)}
            >
              <img src={logo} alt="" aria-hidden="true" className="h-9 w-auto shrink-0" />
              <span className="min-w-0">
                <span className="block font-display text-lg font-extrabold leading-tight tracking-tight text-white">
                  AgriAI
                </span>
                {/* Tagline phải gọn trong 64px chiều cao của header, không xuống dòng. */}
                <span className="block truncate text-[0.6875rem] leading-tight text-[#8FA79A]">
                  {t('smartAgriculture')}
                </span>
              </span>
            </Link>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg p-1.5 text-[#A7BCB0] transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime lg:hidden"
              aria-label={t('closeMenu')}
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>

          <nav
            aria-label="Điều hướng chính"
            className="flex-1 space-y-0.5 overflow-y-auto px-3 py-5 scrollbar-hide"
          >
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item);
              return (
                <Link
                  key={item.key}
                  to={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? 'page' : undefined}
                  className={linkClass(active)}
                >
                  {active && (
                    <span
                      aria-hidden="true"
                      className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-field-lime"
                    />
                  )}
                  <Icon
                    className={`h-[1.125rem] w-[1.125rem] shrink-0 ${
                      active ? 'text-field-lime' : 'text-[#7A9184] group-hover:text-white'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="truncate">{item.name[language]}</span>
                </Link>
              );
            })}
          </nav>

          <div className="shrink-0 border-t border-white/10 p-4">
            <Link
              to="/quality"
              onClick={() => setOpen(false)}
              className="flex min-h-11 w-full items-center justify-center gap-2 rounded-full bg-field-lime px-4 py-2.5 text-sm font-bold text-field-ink transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field-lime motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <Camera className="h-4 w-4" aria-hidden="true" />
              {t('newAnalysis')}
            </Link>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
