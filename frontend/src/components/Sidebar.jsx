import {
  BarChart3,
  Bell,
  Bot,
  CalendarDays,
  Camera,
  CloudSun,
  LayoutDashboard,
  Settings,
  Sprout,
  TrendingUp,
  X,
} from 'lucide-react';
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
    match: ['/dashboard', '/dashboard-new'],
  },
  {
    key: 'pricing',
    name: { vi: 'Định giá nông sản', en: 'Crop Pricing' },
    href: '/pricing',
    icon: TrendingUp,
    match: ['/pricing', '/pricing-dashboard', '/crop'],
  },
  {
    key: 'quality',
    name: { vi: 'Kiểm định chất lượng', en: 'Quality Check' },
    href: '/quality',
    icon: Camera,
    match: ['/quality', '/quality-check'],
  },
  {
    key: 'harvest',
    name: { vi: 'Dự báo thu hoạch', en: 'Harvest Forecast' },
    href: '/harvest',
    icon: Sprout,
    match: ['/harvest', '/harvest-forecast'],
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
    match: ['/market', '/market-strategy'],
  },
  {
    key: 'alerts',
    name: { vi: 'Cảnh báo giá', en: 'Price Alerts' },
    href: '/alerts',
    icon: Bell,
    match: ['/alerts', '/alerts-management'],
  },
  {
    key: 'aiAssistant',
    name: { vi: 'Trợ lý AI', en: 'AI Assistant' },
    href: '/ai-chat',
    icon: Bot,
    match: ['/ai-chat'],
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

const Sidebar = ({ open, setOpen }) => {
  const location = useLocation();
  const { language, t } = useLanguage();

  const isActive = (item) =>
    item.match.some((path) =>
      path === item.href ? location.pathname === path : location.pathname.startsWith(path)
    );

  return (
    <>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-gray-600/75 lg:hidden"
          onClick={() => setOpen(false)}
          aria-label={t('closeMenu')}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-gray-200 bg-white transition-transform duration-300 ease-in-out lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center justify-between border-b border-gray-200 px-6">
            <Link to="/" className="flex items-center gap-3" onClick={() => setOpen(false)}>
              <img src={logo} alt="AgriAI Logo" className="h-10 w-auto" />
              <span>
                <span className="block text-xl font-bold text-gray-900">AgriAI</span>
                <span className="block text-xs text-gray-500">{t('smartAgriculture')}</span>
              </span>
            </Link>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 lg:hidden"
              aria-label={t('closeMenu')}
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-6 scrollbar-hide">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item);
              return (
                <Link
                  key={item.key}
                  to={item.href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center rounded-lg px-4 py-3 text-sm font-medium transition-colors ${active ? 'bg-emerald-50 text-emerald-700' : 'text-gray-700 hover:bg-gray-50'}`}
                >
                  <Icon className={`mr-3 h-5 w-5 ${active ? 'text-emerald-600' : 'text-gray-400'}`} />
                  {item.name[language]}
                </Link>
              );
            })}
          </nav>

          <div className="border-t border-gray-200 p-4">
            <Link
              to="/quality-check"
              onClick={() => setOpen(false)}
              className="flex w-full items-center justify-center rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white transition-colors hover:bg-emerald-700"
            >
              {t('newAnalysis')}
            </Link>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
