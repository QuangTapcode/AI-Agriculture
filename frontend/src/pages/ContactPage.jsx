import { ArrowRight, CheckCircle2, Database, Loader2, MessageSquareText } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';
import Reveal from '../components/ui/Reveal';
import { publicApi } from '../services/publicApi';

const initialForm = {
  name: '', email: '', phone: '', topic: 'technical', message: '', website: '',
};

const topics = [
  ['technical', 'Hỗ trợ kỹ thuật'],
  ['account', 'Tài khoản'],
  ['service', 'Dịch vụ'],
  ['data', 'Kết nối dữ liệu'],
  ['other', 'Nội dung khác'],
];

const inputClass = 'mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-950 outline-none transition focus:border-emerald-700 focus:ring-4 focus:ring-emerald-100';

export default function ContactPage() {
  const [form, setForm] = useState(initialForm);
  const [state, setState] = useState({ status: 'idle', message: '', receipt: null });

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.email.trim() && !form.phone.trim()) {
      setState({ status: 'error', message: 'Vui lòng nhập email hoặc số điện thoại.', receipt: null });
      return;
    }
    setState({ status: 'loading', message: '', receipt: null });
    try {
      const receipt = await publicApi.createContactRequest(form);
      setState({ status: 'success', message: '', receipt });
      setForm(initialForm);
    } catch (error) {
      setState({ status: 'error', message: error.message || 'Không thể lưu yêu cầu.', receipt: null });
    }
  };

  return (
    <main className="min-h-screen bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(186,255,89,0.12),transparent_28%)]" />
        <div className="relative mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-28">
          <Reveal>
            <p className="font-display text-sm font-bold uppercase tracking-[0.22em] text-field-lime">Liên hệ</p>
            <h1 className="mt-5 max-w-4xl font-display text-4xl font-extrabold leading-[1.05] tracking-[-0.04em] sm:text-6xl">
              Một yêu cầu. Một mã xác nhận.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              Yêu cầu chỉ được báo thành công sau khi database xác nhận. Email quản trị là kênh phụ và không ảnh hưởng dữ liệu đã lưu.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="bg-field-canvas px-5 py-16 text-slate-950 sm:px-8 lg:py-24">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Reveal>
            <form onSubmit={handleSubmit} className="field-panel bg-white p-6 sm:p-8" noValidate>
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">Gửi yêu cầu</p>
              <h2 className="mt-2 font-display text-3xl font-bold tracking-tight">Bạn cần hỗ trợ điều gì?</h2>

              {state.status === 'error' && (
                <div role="alert" className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-800">{state.message}</div>
              )}
              {state.status === 'success' && state.receipt?.id && (
                <div role="status" className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
                  <div className="flex items-center gap-2 font-bold"><CheckCircle2 className="h-5 w-5" aria-hidden="true" /> Đã lưu vào hệ thống</div>
                  <p className="mt-1 text-sm">Mã yêu cầu #{state.receipt.id}. Trạng thái: mới.</p>
                </div>
              )}

              <div className="mt-7 grid gap-5 sm:grid-cols-2">
                <label className="text-sm font-bold text-slate-700">Họ và tên
                  <input name="name" value={form.name} onChange={updateField} className={inputClass} autoComplete="name" required minLength={2} />
                </label>
                <label className="text-sm font-bold text-slate-700">Chủ đề
                  <select name="topic" value={form.topic} onChange={updateField} className={inputClass}>
                    {topics.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
                <label className="text-sm font-bold text-slate-700">Email
                  <input name="email" type="email" value={form.email} onChange={updateField} className={inputClass} autoComplete="email" />
                </label>
                <label className="text-sm font-bold text-slate-700">Số điện thoại
                  <input name="phone" type="tel" value={form.phone} onChange={updateField} className={inputClass} autoComplete="tel" />
                </label>
                <label className="text-sm font-bold text-slate-700 sm:col-span-2">Nội dung
                  <textarea name="message" value={form.message} onChange={updateField} className={`${inputClass} resize-y`} rows={6} required minLength={10} />
                </label>
                <label className="absolute -left-[9999px]" aria-hidden="true">Website
                  <input name="website" value={form.website} onChange={updateField} tabIndex={-1} autoComplete="off" />
                </label>
              </div>
              <p className="mt-4 text-sm text-slate-500">Cần ít nhất email hoặc số điện thoại để nhận phản hồi.</p>
              <button type="submit" disabled={state.status === 'loading'} className="field-button-primary mt-6 w-full disabled:cursor-wait disabled:opacity-60 sm:w-auto">
                {state.status === 'loading' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <MessageSquareText className="h-4 w-4" aria-hidden="true" />}
                {state.status === 'loading' ? 'Đang lưu…' : 'Gửi yêu cầu'}
              </button>
            </form>
          </Reveal>

          <aside className="space-y-5">
            <Reveal delay={100}>
              <div className="field-light-card p-6">
                <Database className="h-6 w-6 text-emerald-700" aria-hidden="true" />
                <h2 className="mt-5 font-display text-xl font-bold">Cách hệ thống ghi nhận</h2>
                <ol className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                  <li>1. Kiểm tra dữ liệu liên hệ.</li><li>2. Lưu yêu cầu với trạng thái mới.</li><li>3. Trả mã xác nhận từ database.</li>
                </ol>
              </div>
            </Reveal>
            <Reveal delay={160}>
              <div className="rounded-[1.75rem] bg-field-deep p-6 text-white shadow-field">
                <h2 className="font-display text-xl font-bold">Tự tra cứu trước</h2>
                <p className="mt-2 leading-7 text-slate-300">Các công cụ đang hoạt động nằm trong hệ thống sau khi đăng nhập.</p>
                <Link to="/features" className="mt-5 inline-flex items-center gap-2 font-bold text-field-lime">Xem tính năng <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
              </div>
            </Reveal>
          </aside>
        </div>
      </section>
      <PublicFooter />
    </main>
  );
}
