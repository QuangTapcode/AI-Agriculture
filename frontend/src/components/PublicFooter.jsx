import { ArrowUpRight, Leaf } from 'lucide-react';
import { Link } from 'react-router-dom';

const footerLinks = [
  { label: 'Tính năng', to: '/features' },
  { label: 'Bài viết', to: '/articles' },
  { label: 'Gói dịch vụ', to: '/pricing-plans' },
  { label: 'Liên hệ', to: '/contact' },
];

export default function PublicFooter() {
  return (
    <footer className="border-t border-white/10 bg-field-ink text-slate-300">
      <div className="mx-auto max-w-[1440px] px-4 py-12 sm:px-6 lg:px-10">
        <div className="grid gap-10 md:grid-cols-[1.3fr_.7fr] md:items-end">
          <div className="max-w-xl">
            <div className="flex items-center gap-3 text-white"><span className="grid h-10 w-10 place-items-center rounded-xl bg-field-lime text-field-ink"><Leaf className="h-5 w-5" /></span><span className="font-display text-xl font-extrabold">AgriAI</span></div>
            <p className="mt-5 max-w-md text-sm leading-6 text-slate-400">Theo dõi dữ liệu nông nghiệp, quản lý mùa vụ và tra cứu kiến thức từ một hệ thống thống nhất.</p>
          </div>
          <nav className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:justify-self-end" aria-label="Liên kết cuối trang">
            {footerLinks.map((link) => <Link key={link.to} to={link.to} className="inline-flex items-center gap-1 font-semibold hover:text-field-lime">{link.label}<ArrowUpRight className="h-3.5 w-3.5" /></Link>)}
          </nav>
        </div>
        <div className="mt-10 border-t border-white/10 pt-5 text-xs text-slate-400">© {new Date().getFullYear()} AgriAI</div>
      </div>
    </footer>
  );
}
