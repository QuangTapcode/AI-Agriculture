import { ArrowDownRight, Bot, CloudSun, Database, Sprout, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';
import Reveal from '../components/ui/Reveal';
import TiltCard from '../components/ui/TiltCard';

const signals = [
  { icon: CloudSun, title: 'Theo dõi điều kiện canh tác', description: 'Xem thời tiết theo khu vực, thời điểm cập nhật và cảnh báo liên quan đến cây trồng.', action: 'Mở thời tiết', to: '/weather' },
  { icon: TrendingUp, title: 'Đối chiếu giá và thị trường', description: 'Giá, xu hướng và nguồn dữ liệu được đặt cạnh nhau để bạn biết mình đang xem gì.', action: 'Mở định giá', to: '/pricing' },
  { icon: Bot, title: 'Hỏi trợ lý có nguồn', description: 'Trợ lý tìm bằng chứng trong kho tài liệu trước khi soạn câu trả lời.', action: 'Hỏi AgriAI', to: '/ai-chat' },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative isolate min-h-[calc(100vh-72px)] overflow-hidden">
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_78%_18%,rgba(22,76,55,.9),transparent_34%),radial-gradient(circle_at_12%_58%,rgba(29,78,45,.48),transparent_35%)]" />
        <div aria-hidden="true" className="absolute inset-0 opacity-[.16] [background-image:repeating-radial-gradient(ellipse_at_75%_80%,transparent_0_22px,rgba(186,255,89,.28)_23px_24px)]" />
        <div className="relative mx-auto grid min-h-[calc(100vh-72px)] max-w-[1440px] items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.02fr_.98fr] lg:px-10 lg:py-20">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-field-lime">Từ tín hiệu đến hành động</p>
            <h1 className="mt-6 font-display text-5xl font-extrabold leading-[.94] tracking-[-.055em] sm:text-6xl lg:text-[5.75rem]">Hiểu mùa vụ.<br />Quyết định sớm.</h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-slate-300">Theo dõi thời tiết, giá, mùa vụ và kiến thức nông nghiệp trong cùng một luồng làm việc.</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link to="/login" className="field-button-primary">Bắt đầu sử dụng <ArrowDownRight className="h-4 w-4" /></Link>
              <Link to="/features" className="field-button-secondary">Xem cách hoạt động</Link>
            </div>
          </div>
          <div className="relative mx-auto h-[510px] w-full max-w-[580px] sm:h-[590px]">
            <div aria-hidden="true" className="absolute inset-[8%] rounded-full border border-field-lime/20 [transform:rotateX(68deg)]" />
            <div aria-hidden="true" className="absolute inset-[20%] rounded-full border border-dashed border-white/15 [transform:rotateX(68deg)]" />
            <TiltCard className="absolute left-1/2 top-16 w-[min(92%,430px)] -translate-x-1/2">
              <article className="field-panel p-5 sm:p-7">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div><p className="text-xs font-semibold text-slate-400">Không gian làm việc</p><h2 className="mt-1 font-display text-2xl font-bold">Tín hiệu cần xem</h2></div>
                  <span className="max-w-[10rem] rounded-full bg-field-lime/10 px-3 py-1 text-center text-xs font-semibold leading-5 text-field-lime">Theo dữ liệu của bạn</span>
                </div>
                <div className="mt-8 grid gap-3">
                  <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4"><span className="text-xs text-slate-400">Thời tiết</span><p className="mt-1 font-semibold">Chọn khu vực để kiểm tra</p></div>
                  <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4"><span className="text-xs text-slate-400">Giá nông sản</span><p className="mt-1 font-semibold">Chọn cây trồng để đối chiếu</p></div>
                  <div className="rounded-2xl border border-white/10 bg-white/[.045] p-4"><span className="text-xs text-slate-400">Kho tài liệu</span><p className="mt-1 font-semibold">Kiểm tra sau khi đăng nhập</p></div>
                </div>
              </article>
            </TiltCard>
            <div className="absolute bottom-10 left-0 rounded-2xl border border-white/10 bg-field-deep/85 p-4 shadow-field backdrop-blur-xl sm:left-4"><Database className="h-5 w-5 text-field-lime" /><p className="mt-2 text-sm font-semibold">Nguồn đi cùng kết quả</p></div>
            <div className="absolute bottom-28 right-0 rounded-2xl border border-white/10 bg-field-deep/85 p-4 shadow-field backdrop-blur-xl sm:right-4"><Sprout className="h-5 w-5 text-field-lime" /><p className="mt-2 text-sm font-semibold">Theo ngữ cảnh mùa vụ</p></div>
          </div>
        </div>
      </section>

      <section className="relative mx-auto max-w-[1440px] px-4 py-24 sm:px-6 lg:px-10 lg:py-32">
        <Reveal className="max-w-3xl"><p className="text-sm font-semibold text-field-lime">Ba việc chính</p><h2 className="mt-4 font-display text-4xl font-extrabold tracking-[-.04em] sm:text-5xl lg:text-6xl">Nhìn đúng tín hiệu trước khi hành động.</h2></Reveal>
        <div className="mt-12 grid gap-4 lg:grid-cols-3">
          {signals.map((signal, index) => { const Icon = signal.icon; return (
            <Reveal key={signal.title} delay={index * 80}>
              <Link to={signal.to} className="group block min-h-[320px] rounded-[2rem] border border-white/10 bg-white/[.045] p-7 transition duration-300 hover:-translate-y-2 hover:border-field-lime/30 hover:bg-white/[.075]">
                <Icon className="h-7 w-7 text-field-lime" /><h3 className="mt-16 font-display text-2xl font-bold">{signal.title}</h3><p className="mt-4 leading-7 text-slate-400">{signal.description}</p><span className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-white">{signal.action}<ArrowDownRight className="h-4 w-4 transition-transform group-hover:translate-x-1 group-hover:translate-y-1" /></span>
              </Link>
            </Reveal>
          ); })}
        </div>
      </section>

      <section className="border-y border-white/10 bg-field-deep">
        <div className="mx-auto grid max-w-[1440px] gap-14 px-4 py-24 sm:px-6 lg:grid-cols-[.85fr_1.15fr] lg:items-center lg:px-10 lg:py-32">
          <Reveal>
            <p className="text-sm font-semibold text-field-lime">Trợ lý nông nghiệp</p><h2 className="mt-4 font-display text-4xl font-extrabold tracking-[-.04em] sm:text-5xl">Câu trả lời bắt đầu từ bằng chứng.</h2>
            <ol className="mt-10 space-y-3 text-slate-300">{['Nhận cây trồng, khu vực và vấn đề', 'Tìm đoạn tài liệu phù hợp', 'Trả lời kèm nguồn và giới hạn'].map((item, index) => <li key={item} className="flex items-center gap-4 rounded-2xl border border-white/10 p-4"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-field-lime/10 font-semibold text-field-lime">{index + 1}</span>{item}</li>)}</ol>
          </Reveal>
          <Reveal delay={100}>
            <div className="rounded-[2.25rem] bg-field-mist p-7 text-field-ink shadow-field sm:p-10">
              <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-field-ink text-field-lime"><Bot className="h-5 w-5" /></span><span className="font-display font-bold">AgriAI</span></div>
              <h3 className="mt-9 font-display text-2xl font-extrabold sm:text-3xl">Hỏi theo tình trạng thực tế của ruộng.</h3><p className="mt-4 leading-7 text-slate-600">Cung cấp cây trồng, khu vực và dấu hiệu bạn quan sát được. Trợ lý sẽ cho biết nguồn nào đã được dùng.</p><Link to="/ai-chat" className="mt-7 inline-flex min-h-11 items-center rounded-full bg-field-ink px-5 text-sm font-bold text-white hover:bg-emerald-900">Mở trợ lý</Link>
            </div>
          </Reveal>
        </div>
      </section>
      <PublicFooter />
    </main>
  );
}
