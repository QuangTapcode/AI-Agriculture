import { Eye, EyeOff, LockKeyhole, ShieldCheck, Sprout } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage({ initialMode = 'login' }) {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState(initialMode === 'register' ? 'register' : 'login');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({ name: '', phone: '', email: '', password: '' });
  const isRegister = mode === 'register';

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError('');
    setSuccess('');
  };

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (!form.email.trim() || !form.password) {
      setError('Nhập email và mật khẩu để tiếp tục.');
      return;
    }
    if (isRegister && !form.name.trim()) {
      setError('Nhập họ tên để tạo tài khoản.');
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register({ fullName: form.name.trim(), email: form.email.trim(), password: form.password, phoneNumber: form.phone.trim() || null, zaloId: null, region: null });
        setSuccess('Tài khoản đã được tạo. Đang mở hệ thống…');
      } else {
        await login({ email: form.email.trim(), password: form.password });
        setSuccess('Đăng nhập thành công. Đang mở hệ thống…');
      }
      const returnUrl = sessionStorage.getItem('returnUrl');
      sessionStorage.removeItem('returnUrl');
      window.setTimeout(() => navigate(returnUrl || '/dashboard'), 350);
    } catch (requestError) {
      const status = requestError?.response?.status;
      const detail = requestError?.response?.data?.detail || requestError?.response?.data?.message;
      if (status === 503) setError('Máy chủ hoặc cơ sở dữ liệu chưa sẵn sàng. Thử lại sau.');
      else if (status === 401) setError('Email hoặc mật khẩu không đúng.');
      else if (status === 409) setError('Email này đã được đăng ký.');
      else if (status === 422) setError(Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail || 'Thông tin chưa hợp lệ.');
      else if (!requestError?.response) setError('Không kết nối được máy chủ. Kiểm tra backend rồi thử lại.');
      else setError(detail || 'Không thể hoàn tất yêu cầu.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen overflow-x-hidden bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative min-h-[calc(100vh-72px)] overflow-hidden">
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_12%_24%,rgba(22,76,55,.92),transparent_34%),radial-gradient(circle_at_88%_82%,rgba(101,163,13,.18),transparent_30%)]" />
        <div className="relative mx-auto grid min-h-[calc(100vh-72px)] max-w-[1280px] items-center gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[.9fr_1.1fr] lg:px-10 lg:py-16">
          <div className="max-w-xl">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-field-lime text-field-ink"><Sprout className="h-6 w-6" /></span>
            <h1 className="mt-7 font-display text-4xl font-extrabold tracking-[-.045em] sm:text-5xl lg:text-6xl">Dữ liệu mùa vụ của bạn, trong một nơi.</h1>
            <p className="mt-6 max-w-lg text-lg leading-8 text-slate-300">Đăng nhập để mở dữ liệu thuộc tài khoản, lịch sử phân tích và kho tài liệu của bạn.</p>
            <div className="mt-9 space-y-3 text-sm text-slate-300">
              <p className="flex items-center gap-3"><ShieldCheck className="h-5 w-5 text-field-lime" /> Dữ liệu được tách theo tài khoản</p>
              <p className="flex items-center gap-3"><LockKeyhole className="h-5 w-5 text-field-lime" /> Các công cụ bên trong yêu cầu xác thực</p>
            </div>
          </div>

          <div className="mx-auto w-full max-w-md rounded-[2rem] bg-white p-6 text-slate-950 shadow-field sm:p-8">
            <div className="grid grid-cols-2 rounded-full bg-slate-100 p-1" role="tablist" aria-label="Tài khoản">
              <button type="button" role="tab" aria-selected={!isRegister} onClick={() => switchMode('login')} className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${!isRegister ? 'bg-field-ink text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}>Đăng nhập</button>
              <button type="button" role="tab" aria-selected={isRegister} onClick={() => switchMode('register')} className={`rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${isRegister ? 'bg-field-ink text-white shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}>Đăng ký</button>
            </div>
            <div className="mt-8"><h2 className="font-display text-3xl font-extrabold tracking-tight">{isRegister ? 'Tạo tài khoản' : 'Chào mừng trở lại'}</h2><p className="mt-2 text-sm text-slate-500">{isRegister ? 'Dùng thông tin thật của bạn để bắt đầu.' : 'Nhập thông tin tài khoản để tiếp tục.'}</p></div>

            <form onSubmit={handleSubmit} className="mt-7 space-y-4" noValidate>
              {isRegister ? <label className="block text-sm font-semibold text-slate-700" htmlFor="auth-name">Họ tên<input id="auth-name" autoComplete="name" value={form.name} onChange={(event) => updateField('name', event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-100" /></label> : null}
              {isRegister ? <label className="block text-sm font-semibold text-slate-700" htmlFor="auth-phone">Số điện thoại <span className="font-normal text-slate-400">(không bắt buộc)</span><input id="auth-phone" autoComplete="tel" inputMode="tel" value={form.phone} onChange={(event) => updateField('phone', event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-100" /></label> : null}
              <label className="block text-sm font-semibold text-slate-700" htmlFor="auth-email">Email<input id="auth-email" type="email" autoComplete="email" value={form.email} onChange={(event) => updateField('email', event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-100" /></label>
              <label className="block text-sm font-semibold text-slate-700" htmlFor="auth-password">Mật khẩu<span className="relative mt-2 block"><input id="auth-password" type={showPassword ? 'text' : 'password'} autoComplete={isRegister ? 'new-password' : 'current-password'} value={form.password} onChange={(event) => updateField('password', event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 pr-12 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-100" /><button type="button" onClick={() => setShowPassword((value) => !value)} className="absolute inset-y-0 right-1 grid w-11 place-items-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}>{showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}</button></span></label>
              {error ? <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">{error}</div> : null}
              {success ? <div role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">{success}</div> : null}
              <button type="submit" disabled={loading} className="mt-2 flex min-h-12 w-full items-center justify-center rounded-full bg-field-ink px-5 font-bold text-white transition hover:bg-emerald-900 disabled:cursor-wait disabled:opacity-60">{loading ? 'Đang xử lý…' : isRegister ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
            </form>
            <p className="mt-6 text-center text-sm text-slate-500">{isRegister ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'} <button type="button" onClick={() => switchMode(isRegister ? 'login' : 'register')} className="font-semibold text-emerald-800 hover:text-emerald-950">{isRegister ? 'Đăng nhập' : 'Đăng ký'}</button></p>
            <Link to="/" className="mt-4 block text-center text-sm text-slate-400 hover:text-slate-700">Về trang chủ</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
