import { ArrowRight, BadgeCheck, Receipt } from 'lucide-react';
import { Link } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';
import EmptyState from '../components/ui/EmptyState';
import Reveal from '../components/ui/Reveal';

export default function SubscriptionPricingPage() {
  return (
    <main className="min-h-screen bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(186,255,89,0.13),transparent_30%)]" />
        <div className="relative mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-28">
          <Reveal>
            <p className="font-display text-sm font-bold uppercase tracking-[0.22em] text-field-lime">Gói dịch vụ</p>
            <h1 className="mt-5 max-w-4xl font-display text-4xl font-extrabold leading-[1.05] tracking-[-0.04em] sm:text-6xl">
              Giá rõ ràng khi dịch vụ sẵn sàng.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              Billing chưa được triển khai. AgriAI sẽ không hiển thị mức giá, hạn mức hay quyền lợi chưa được cấu hình trong hệ thống.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="bg-field-canvas px-5 py-16 text-slate-950 sm:px-8 lg:py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <div className="field-panel bg-white p-3 sm:p-5">
              <EmptyState
                icon={Receipt}
                title="Gói dịch vụ chưa được công bố"
                description="Bạn vẫn có thể đăng nhập và sử dụng các chức năng đang mở. Bảng giá sẽ chỉ xuất hiện sau khi có cấu hình billing được xác nhận."
                action={(
                  <Link to="/register" className="field-button-primary">
                    Tạo tài khoản <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Link>
                )}
              />
            </div>
          </Reveal>

          <Reveal delay={100} className="mt-8">
            <div className="field-light-card flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-800">
                  <BadgeCheck className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="font-display text-xl font-bold">Cần trao đổi nhu cầu?</h2>
                  <p className="mt-1 text-slate-600">Gửi yêu cầu; hệ thống sẽ cấp mã xác nhận sau khi lưu thành công.</p>
                </div>
              </div>
              <Link to="/contact" className="field-button-secondary shrink-0">Liên hệ</Link>
            </div>
          </Reveal>
        </div>
      </section>
      <PublicFooter />
    </main>
  );
}
