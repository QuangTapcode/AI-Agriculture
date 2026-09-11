import { ArrowUpRight, Bot, CloudSun, Database, ScanSearch, Sprout, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import AgriNavbar from '../components/AgriNavbar';
import PublicFooter from '../components/PublicFooter';
import Reveal from '../components/ui/Reveal';

const workflows = [
  { icon: CloudSun, title: 'Theo dõi điều kiện canh tác', description: 'Chọn khu vực, xem thời tiết và đọc cảnh báo kèm thời điểm cập nhật.', steps: ['Chọn khu vực', 'Kiểm tra nguồn', 'Lưu cảnh báo'], to: '/weather' },
  { icon: TrendingUp, title: 'Đối chiếu giá và thị trường', description: 'Chọn nông sản và vùng để so sánh dữ liệu giá đang có trong hệ thống.', steps: ['Chọn nông sản', 'Đọc trạng thái dữ liệu', 'So sánh khu vực'], to: '/pricing' },
  { icon: Bot, title: 'Hỏi trợ lý có nguồn', description: 'Đặt câu hỏi theo ngữ cảnh và mở tài liệu gốc từ phần trích dẫn.', steps: ['Mô tả tình trạng', 'Tra cứu tài liệu', 'Kiểm tra trích dẫn'], to: '/ai-chat' },
];

const capabilities = [
  { icon: ScanSearch, title: 'Kiểm định chất lượng', text: 'Phân tích ảnh nông sản bằng mô hình đang được cấu hình.', to: '/quality' },
  { icon: Sprout, title: 'Quản lý mùa vụ', text: 'Lưu và theo dõi mùa vụ thuộc tài khoản của bạn.', to: '/season-management' },
  { icon: Database, title: 'Kho tài liệu', text: 'Theo dõi tài liệu đã duyệt và trạng thái lập chỉ mục.', to: '/knowledge-documents' },
];

export default function FeaturesPage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-field-ink text-white">
      <AgriNavbar />
      <section className="relative overflow-hidden border-b border-white/10">
        <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_85%_10%,rgba(22,76,55,.9),transparent_38%)]" />
        <div className="relative mx-auto max-w-[1440px] px-4 py-20 sm:px-6 lg:px-10 lg:py-28">
          <p className="text-sm font-semibold text-field-lime">Cách AgriAI hỗ trợ</p>
          <h1 className="mt-5 max-w-5xl font-display text-5xl font-extrabold leading-[.98] tracking-[-.05em] sm:text-6xl lg:text-7xl">Mỗi công cụ dẫn tới một quyết định rõ ràng.</h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">Chọn đúng luồng làm việc, kiểm tra nguồn dữ liệu và tiếp tục trong hệ thống.</p>
        </div>
      </section>
      <section className="mx-auto max-w-[1440px] px-4 py-24 sm:px-6 lg:px-10">
        <div className="space-y-5">
          {workflows.map((workflow, index) => { const Icon = workflow.icon; return (
            <Reveal key={workflow.title} delay={index * 70}>
              <article className="group grid gap-8 rounded-[2rem] border border-white/10 bg-white/[.045] p-6 transition duration-300 hover:border-field-lime/30 hover:bg-white/[.07] sm:p-8 lg:grid-cols-[.8fr_1.2fr] lg:items-center">
                <div><span className="grid h-12 w-12 place-items-center rounded-2xl bg-field-lime/10 text-field-lime"><Icon className="h-6 w-6" /></span><h2 className="mt-6 font-display text-3xl font-bold tracking-tight">{workflow.title}</h2><p className="mt-3 max-w-xl leading-7 text-slate-400">{workflow.description}</p></div>
                <div className="grid gap-3 sm:grid-cols-3">{workflow.steps.map((step, stepIndex) => <div key={step} className="rounded-2xl border border-white/10 bg-field-deep p-4"><span className="text-xs font-semibold text-field-lime">Bước {stepIndex + 1}</span><p className="mt-2 font-semibold">{step}</p></div>)}</div>
                <Link to={workflow.to} className="inline-flex items-center gap-2 text-sm font-semibold text-field-lime lg:col-start-2">Mở công cụ <ArrowUpRight className="h-4 w-4 transition-transform group-hover:translate-x-1 group-hover:-translate-y-1" /></Link>
              </article>
            </Reveal>
          ); })}
        </div>
      </section>
      <section className="bg-field-mist text-field-ink">
        <div className="mx-auto max-w-[1440px] px-4 py-24 sm:px-6 lg:px-10">
          <Reveal className="max-w-2xl"><p className="text-sm font-semibold text-emerald-800">Công cụ trong hệ thống</p><h2 className="mt-4 font-display text-4xl font-extrabold tracking-[-.04em] sm:text-5xl">Dữ liệu của bạn được giữ đúng ngữ cảnh.</h2></Reveal>
          <div className="mt-12 grid gap-4 md:grid-cols-3">{capabilities.map((item, index) => { const Icon = item.icon; return <Reveal key={item.title} delay={index * 70}><Link to={item.to} className="group block min-h-64 rounded-[2rem] border border-emerald-950/10 bg-white p-7 transition duration-300 hover:-translate-y-2 hover:shadow-xl"><Icon className="h-6 w-6 text-emerald-800" /><h3 className="mt-14 font-display text-2xl font-bold">{item.title}</h3><p className="mt-3 leading-7 text-slate-600">{item.text}</p></Link></Reveal>; })}</div>
        </div>
      </section>
      <PublicFooter />
    </main>
  );
}
