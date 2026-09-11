import { ArrowLeft, Home } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';

function NotFoundContent() {
  const navigate = useNavigate();
  return (
    <section className="relative flex min-h-[68vh] items-center overflow-hidden bg-field-ink px-5 py-20 text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(186,255,89,0.12),transparent_32%)]" />
      <div className="relative mx-auto w-full max-w-3xl text-center">
        <p className="font-display text-sm font-bold uppercase tracking-[0.3em] text-field-lime">Lỗi 404</p>
        <h1 className="mt-5 font-display text-5xl font-extrabold tracking-[-0.04em] sm:text-7xl">Không tìm thấy trang</h1>
        <p className="mx-auto mt-5 max-w-xl text-lg leading-8 text-slate-300">Đường dẫn có thể đã thay đổi hoặc chưa tồn tại.</p>
        <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
          <button type="button" onClick={() => navigate(-1)} className="field-button-secondary border-white/20 bg-transparent text-white hover:bg-white/10"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Quay lại</button>
          <Link to="/" className="field-button-primary"><Home className="h-4 w-4" aria-hidden="true" /> Về trang chủ</Link>
        </div>
      </div>
    </section>
  );
}

export default function NotFoundPage({ publicLayout = true }) {
  if (!publicLayout) return <NotFoundContent />;
  return <main className="min-h-screen bg-field-ink"><AgriNavbar /><NotFoundContent /><PublicFooter /></main>;
}
