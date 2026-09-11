import { ArrowRight, BookOpen, Library, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';
import EmptyState from '../components/ui/EmptyState';
import Reveal from '../components/ui/Reveal';

export default function ArticlesPage() {
  return (
    <main className="min-h-screen bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_18%,rgba(186,255,89,0.12),transparent_30%)]" />
        <div className="relative mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-28">
          <Reveal>
            <p className="font-display text-sm font-bold uppercase tracking-[0.22em] text-field-lime">Thư viện công khai</p>
            <h1 className="mt-5 max-w-4xl font-display text-4xl font-extrabold leading-[1.05] tracking-[-0.04em] sm:text-6xl">
              Kiến thức chỉ xuất hiện khi đã được kiểm chứng.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              AgriAI chưa có CMS xuất bản bài viết. Tài liệu trong kho RAG vẫn được giữ riêng và không tự động trở thành nội dung công khai.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="bg-field-canvas px-5 py-16 text-slate-950 sm:px-8 lg:py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <div className="field-panel bg-white p-3 sm:p-5">
              <EmptyState
                icon={BookOpen}
                title="Chưa có bài viết đã xác minh"
                description="Khi có quy trình biên tập, nguồn xuất bản và người duyệt rõ ràng, các bài viết mới sẽ xuất hiện tại đây."
                action={(
                  <Link to="/features" className="field-button-primary">
                    Xem tính năng hiện có <ArrowRight className="h-4 w-4" aria-hidden="true" />
                  </Link>
                )}
              />
            </div>
          </Reveal>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <Reveal delay={80}>
              <div className="field-light-card h-full p-6">
                <ShieldCheck className="h-6 w-6 text-emerald-700" aria-hidden="true" />
                <h2 className="mt-5 font-display text-xl font-bold">Có nguồn và quyền xuất bản</h2>
                <p className="mt-2 leading-7 text-slate-600">Mỗi nội dung công khai cần chỉ rõ nguồn, thời điểm cập nhật và trạng thái kiểm duyệt.</p>
              </div>
            </Reveal>
            <Reveal delay={140}>
              <div className="field-light-card h-full p-6">
                <Library className="h-6 w-6 text-emerald-700" aria-hidden="true" />
                <h2 className="mt-5 font-display text-xl font-bold">Tách biệt với kho trợ lý</h2>
                <p className="mt-2 leading-7 text-slate-600">Tài liệu RAG phục vụ tra cứu nội bộ và chỉ được công khai khi có quyền sử dụng phù hợp.</p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
      <PublicFooter />
    </main>
  );
}
