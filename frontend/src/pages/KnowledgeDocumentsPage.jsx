import { BookOpen, CheckCircle2, Clock3, ExternalLink, FileSearch, RefreshCw, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { aiApi } from '../services/aiApi';

const statusLabels = {
  approved: 'Đã duyệt',
  pending: 'Chờ duyệt',
  rejected: 'Không đạt',
  failed: 'Lỗi',
  superseded: 'Bản cũ',
};

const statusStyles = {
  approved: 'bg-emerald-50 text-emerald-700',
  pending: 'bg-amber-50 text-amber-700',
  rejected: 'bg-orange-50 text-orange-700',
  failed: 'bg-red-50 text-red-700',
  superseded: 'bg-gray-100 text-gray-600',
};

const formatDate = (value) => value
  ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
  : '—';

const DocumentStatus = ({ document }) => (
  <div className="flex flex-wrap items-center gap-2">
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusStyles[document.status] || statusStyles.superseded}`}>
      {statusLabels[document.status] || document.status}
    </span>
    {document.indexed && <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700"><CheckCircle2 size={13} />Đã lập chỉ mục</span>}
    {document.is_new && <span className="rounded-full bg-green-600 px-2 py-1 text-xs font-semibold text-white">Mới</span>}
  </div>
);

export function KnowledgeDocumentsTable({ documents }) {
  if (!documents.length) {
    return <div className="rounded-2xl border border-dashed bg-white px-6 py-12 text-center text-gray-600">
      <FileSearch className="mx-auto mb-3" size={34} />
      Không có tài liệu phù hợp với bộ lọc.
    </div>;
  }

  return <div className="space-y-3">
    {documents.map((document) => <article key={document.id} className="min-w-0 rounded-2xl border bg-white p-4 shadow-sm">
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <DocumentStatus document={document} />
          <h2 className="mt-3 break-words font-semibold text-gray-900 [overflow-wrap:anywhere]">{document.title}</h2>
          <p className="mt-1 break-words text-sm text-gray-600 [overflow-wrap:anywhere]">{document.source_name}</p>
        </div>
        {document.source_url && <a href={document.source_url} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-emerald-700 hover:underline">
          Mở nguồn <ExternalLink size={15} />
        </a>}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 text-sm sm:grid-cols-3 xl:grid-cols-6">
        <div><dt className="text-xs text-gray-600">Chủ đề</dt><dd className="mt-1 text-gray-700">{document.crop || '—'}</dd></div>
        <div><dt className="text-xs text-gray-600">Khu vực</dt><dd className="mt-1 text-gray-700">{document.region || '—'}</dd></div>
        <div><dt className="text-xs text-gray-600">Phiên bản</dt><dd className="mt-1 text-gray-700">v{document.version}</dd></div>
        <div><dt className="text-xs text-gray-600">Chất lượng</dt><dd className="mt-1 text-gray-700">{document.quality_score == null ? '—' : `${Math.round(document.quality_score * 100)}%`}</dd></div>
        <div><dt className="text-xs text-gray-600">Embedding</dt><dd className="mt-1 text-gray-700">{document.chunks} đoạn</dd></div>
        <div><dt className="text-xs text-gray-600">Ngày nạp</dt><dd className="mt-1 text-gray-700">{formatDate(document.fetched_at)}</dd></div>
      </dl>
    </article>)}
  </div>;
}

export default function KnowledgeDocumentsPage() {
  const [catalogue, setCatalogue] = useState({ documents: [], summary: {} });
  const [status, setStatus] = useState('approved');
  const [query, setQuery] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError('');
      try {
        const data = await aiApi.getKnowledgeDocuments({ status, q: query.trim() });
        /*
         * Giữ nguyên hình dạng: một phản hồi thiếu `documents` từng làm
         * `catalogue.documents.filter()` ném lỗi và hạ cả trang xuống
         * error boundary thay vì hiện danh sách rỗng.
         */
        if (active) {
          setCatalogue({
            documents: Array.isArray(data?.documents) ? data.documents : [],
            summary: data?.summary && typeof data.summary === 'object' ? data.summary : {},
          });
        }
      } catch (err) {
        if (active) setError(err.message || 'Không tải được danh sách tài liệu.');
      } finally {
        if (active) setLoading(false);
      }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [status, query, refreshKey]);

  const summary = catalogue.summary || {};
  const newCount = catalogue.documents.filter((document) => document.is_new).length;

  return <div className="mx-auto w-full max-w-7xl space-y-6">
    <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex items-center gap-2 text-emerald-700"><BookOpen size={22} /><span className="text-sm font-semibold">Kho tri thức RAG</span></div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Tài liệu đã nạp</h1>
        <p className="mt-2 text-sm text-gray-600">Theo dõi tài liệu mới, kết quả kiểm tra chất lượng và trạng thái lập chỉ mục.</p>
      </div>
      <div className="flex gap-2">
        <Link to="/ai-chat" className="rounded-xl border bg-white px-4 py-2 text-sm font-medium text-gray-700">Về Trợ lý</Link>
        <button onClick={() => setRefreshKey((value) => value + 1)} disabled={loading} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} />Tải lại</button>
      </div>
    </header>

    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <div className="rounded-2xl border bg-white p-4"><p className="text-sm text-gray-600">Đã duyệt</p><strong className="mt-2 block text-2xl">{summary.approved ?? '—'}</strong></div>
      <div className="rounded-2xl border bg-white p-4"><p className="text-sm text-gray-600">Đã lập chỉ mục</p><strong className="mt-2 block text-2xl">{summary.indexed_documents ?? '—'}</strong></div>
      <div className="rounded-2xl border bg-white p-4"><p className="text-sm text-gray-600">Đoạn embedding</p><strong className="mt-2 block text-2xl">{summary.indexed_chunks ?? '—'}</strong></div>
      <div className="rounded-2xl border bg-white p-4"><p className="text-sm text-gray-600">Mới trong lần chạy</p><strong className="mt-2 block text-2xl">{newCount}</strong></div>
    </section>

    <section className="flex flex-col gap-3 rounded-2xl border bg-white p-4 md:flex-row md:items-center">
      <div className="relative min-w-0 flex-1">
        <Search className="absolute left-3 top-2.5 text-gray-600" size={18} aria-hidden="true" />
        <input
          aria-label="Tìm tài liệu theo tiêu đề, nguồn, cây trồng hoặc khu vực"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Tìm tiêu đề, nguồn, cây trồng hoặc khu vực…"
          className="w-full rounded-xl border py-2 pl-10 pr-3 text-sm"
        />
      </div>
      <select
        aria-label="Lọc theo trạng thái tài liệu"
        value={status}
        onChange={(event) => setStatus(event.target.value)}
        className="rounded-xl border bg-white px-3 py-2 text-sm"
      >
        <option value="approved">Đang sử dụng</option>
        <option value="all">Tất cả trạng thái</option>
        <option value="pending">Chờ duyệt</option>
        <option value="rejected">Không đạt</option>
        <option value="failed">Lỗi</option>
        <option value="superseded">Bản cũ</option>
      </select>
      {summary.last_run_started_at && <span className="inline-flex shrink-0 items-center gap-1 text-xs text-gray-600"><Clock3 size={14} />Lần chạy: {formatDate(summary.last_run_started_at)}</span>}
    </section>

    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {loading && !catalogue.documents.length
      ? <div role="status" className="rounded-2xl border bg-white p-10 text-center text-gray-600">Đang tải danh sách tài liệu…</div>
      : <KnowledgeDocumentsTable documents={catalogue.documents} />}
  </div>;
}
