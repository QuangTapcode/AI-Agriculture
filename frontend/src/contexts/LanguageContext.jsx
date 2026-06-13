import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const LANGUAGE_STORAGE_KEY = 'app-language';

const translations = {
  vi: {
    loadingInterface: 'Đang tải giao diện...',
    loadingPage: 'Đang tải trang...',
    openMenu: 'Mở menu',
    closeMenu: 'Đóng menu',
    notifications: 'Thông báo',
    viewNotifications: 'Xem thông báo',
    help: 'Trợ giúp',
    settings: 'Cài đặt',
    profile: 'Hồ sơ',
    account: 'Tài khoản',
    logout: 'Đăng xuất',
    login: 'Đăng nhập',
    smartAgriculture: 'Nông nghiệp thông minh',
    newAnalysis: 'Phân tích mới',
    weather: 'Thời tiết nông vụ',
    dashboard: 'Bảng điều khiển',
    pricing: 'Định giá nông sản',
    quality: 'Kiểm định chất lượng',
    harvest: 'Dự báo thu hoạch',
    seasonManagement: 'Quản lý mùa vụ',
    market: 'Phân tích thị trường',
    alerts: 'Cảnh báo giá',
    aiAssistant: 'Trợ lý AI',
    settingsHeading: 'Cài đặt',
    settingsSubheading: 'Hồ sơ, vùng chuẩn hóa, ma trận thông báo, trạng thái kênh gửi và bảo mật tài khoản.',
    operationSettings: 'Thiết lập vận hành',
    saveSettings: 'Lưu cài đặt',
    language: 'Ngôn ngữ',
    vietnamese: 'Tiếng Việt',
    english: 'English',
    theme: 'Giao diện',
    light: 'Sáng',
    dark: 'Tối',
    system: 'Theo hệ thống',
    regionAndDisplay: 'Vùng và hiển thị',
    sharedRegion: 'Khu vực dùng chung cho giá, thời tiết và bảng điều khiển.',
    normalizedRegion: 'Khu vực chuẩn hóa',
  },
  en: {
    loadingInterface: 'Loading interface...',
    loadingPage: 'Loading page...',
    openMenu: 'Open menu',
    closeMenu: 'Close menu',
    notifications: 'Notifications',
    viewNotifications: 'View notifications',
    help: 'Help',
    settings: 'Settings',
    profile: 'Profile',
    account: 'Account',
    logout: 'Log out',
    login: 'Log in',
    smartAgriculture: 'Smart Agriculture',
    newAnalysis: 'New analysis',
    weather: 'Crop Weather',
    dashboard: 'Dashboard',
    pricing: 'Crop Pricing',
    quality: 'Quality Check',
    harvest: 'Harvest Forecast',
    seasonManagement: 'Season Management',
    market: 'Market Analysis',
    alerts: 'Price Alerts',
    aiAssistant: 'AI Assistant',
    settingsHeading: 'Settings',
    settingsSubheading: 'Profile, normalized region, notification matrix, delivery channel status, and account security.',
    operationSettings: 'Operations settings',
    saveSettings: 'Save settings',
    language: 'Language',
    vietnamese: 'Vietnamese',
    english: 'English',
    theme: 'Theme',
    light: 'Light',
    dark: 'Dark',
    system: 'System',
    regionAndDisplay: 'Region and display',
    sharedRegion: 'Shared region for pricing, weather, and dashboard views.',
    normalizedRegion: 'Normalized region',
  },
};

const LanguageContext = createContext(null);

const getStoredLanguage = () => {
  if (typeof window === 'undefined') {
    return 'vi';
  }

  const storedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return storedLanguage === 'en' ? 'en' : 'vi';
};

export const LanguageProvider = ({ children }) => {
  const [language, setLanguageState] = useState(getStoredLanguage);

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  const setLanguage = (nextLanguage) => {
    const normalizedLanguage = nextLanguage === 'en' ? 'en' : 'vi';
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, normalizedLanguage);
    }
    setLanguageState(normalizedLanguage);
  };

  const value = useMemo(() => {
    const dictionary = translations[language] || translations.vi;

    return {
      language,
      setLanguage,
      t: (key) => dictionary[key] || translations.vi[key] || key,
    };
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }

  return context;
};
