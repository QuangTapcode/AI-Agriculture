import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import logoHeader from '../assets/agri-ai-logo-header.png';
import { useAuth } from '../contexts/AuthContext';

const mainLinks = [
  { label: 'Trang chủ', to: '/' },
  { label: 'Tính năng', to: '/features' },
  { label: 'Bài viết', to: '/articles' },
  { label: 'Gói dịch vụ', to: '/pricing-plans' },
  { label: 'Liên hệ', to: '/contact' },
];

const navClass = ({ isActive }) => `rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
  isActive ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
}`;

export default function AgriNavbar() {
  const [open, setOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-field-ink/85 text-white backdrop-blur-2xl">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
        <div className="flex h-[72px] items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-3 rounded-xl" aria-label="Về trang chủ AgriAI">
            <span className="grid h-10 w-10 place-items-center overflow-hidden rounded-xl bg-field-lime">
              <img src={logoHeader} alt="" className="h-full w-full object-cover" />
            </span>
            <span className="font-display text-lg font-extrabold tracking-tight">AgriAI</span>
          </Link>
          <nav className="hidden items-center gap-1 lg:flex" aria-label="Điều hướng chính">
            {mainLinks.map((link) => <NavLink key={link.to} to={link.to} className={navClass}>{link.label}</NavLink>)}
          </nav>
          <div className="hidden items-center gap-2 lg:flex">
            <Link to="/ai-chat" className="field-button-secondary">Hỏi trợ lý</Link>
            <Link to={isAuthenticated ? '/dashboard' : '/login'} className="field-button-primary">{isAuthenticated ? 'Mở hệ thống' : 'Đăng nhập'}</Link>
          </div>
          <button type="button" onClick={() => setOpen((value) => !value)} className="grid h-11 w-11 place-items-center rounded-full border border-white/15 text-white transition-colors hover:bg-white/10 lg:hidden" aria-label={open ? 'Đóng menu' : 'Mở menu'} aria-expanded={open}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open ? (
          <div className="border-t border-white/10 py-4 lg:hidden">
            <nav className="grid gap-1" aria-label="Điều hướng trên điện thoại">
              {mainLinks.map((link) => <NavLink key={link.to} to={link.to} onClick={() => setOpen(false)} className={({ isActive }) => `${navClass({ isActive })} px-4 py-3`}>{link.label}</NavLink>)}
            </nav>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Link to="/ai-chat" onClick={() => setOpen(false)} className="field-button-secondary">Hỏi trợ lý</Link>
              <Link to={isAuthenticated ? '/dashboard' : '/login'} onClick={() => setOpen(false)} className="field-button-primary">{isAuthenticated ? 'Mở hệ thống' : 'Đăng nhập'}</Link>
            </div>
          </div>
        ) : null}
      </div>
    </header>
  );
}
