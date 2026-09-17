import { BookOpen, Check, CheckCircle2, Clock3, ExternalLink, FileSearch, Loader2, RefreshCw, Search, X } from 'lucide-react';
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

const discoveryStatusLabels = {
  queued: 'Đang chờ worker tìm nguồn…',
  running: 'Đang tìm và kiểm tra tài liệu…',
  indexed: 'Đã kiểm tra đạt và đã áp dụng vào kho chính',
  completed: 'Đã kiểm tra nhưng chưa có tài liệu đạt',
  no_match: 'Chưa tìm thấy nguồn phù hợp',
  failed: 'Tìm nguồn gặp lỗi',
  unavailable: 'Chưa khởi động được tác vụ tìm nguồn',
  disabled: 'Tính năng tự tìm nguồn đang tắt',
};

const verificationLabels = {
  pending: 'Đang kiểm tra',
  passed: 'Đạt kiểm tra',
  checked: 'Đã kiểm tra — chưa đạt để nạp',
  failed: 'Không đạt',
  not_run: 'Chưa chạy',
};

const applyLabels = {
  pending: 'Chờ áp dụng',
  applied: 'Đã áp dụng',
  not_applied: 'Chưa áp dụng',
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
          <p className="mt-1 break-words text-sm text-gray-600 [overflow-wrap:anywhere]"><span className="font-medium text-gray-700">Nguồn:</span> {document.source_name || '—'}</p>
        </div>
        {document.source_url && <a href={document.source_url} target="_blank" rel="noreferrer" className="inline-flex shrink-0 items-center gap-1 text-sm font-medium text-emerald-700 hover:underline">
          Mở nguồn <ExternalLink size={15} />
        </a>}
      </div>
      {document.rejection_reason && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        <p className="font-semibold">Lý do không được áp dụng</p>
        {Array.isArray(document.quality_checks) && document.quality_checks.length > 1
          ? <>
            <p className="mt-1">Tài liệu không đạt các kiểm tra sau:</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-red-700">
              {document.quality_checks.map((check) => <li key={check}>{check}</li>)}
            </ul>
          </>
          : <p className="mt-1">{document.rejection_reason}</p>}
      </div>}
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 text-sm sm:grid-cols-3 xl:grid-cols-6">
        <div><dt className="text-xs text-gray-600">Chủ đề</dt><dd className="mt-1 text-gray-700">{document.crop || '—'}</dd></div>
        <div><dt className="text-xs text-gray-600">Khu vực</dt><dd className="mt-1 text-gray-700">{document.region || '—'}</dd></div>
        <div><dt className="text-xs text-gray-600">Phiên bản</dt><dd className="mt-1 text-gray-700">v{document.version}</dd></div>
        <div><dt className="text-xs text-gray-600">Chất lượng</dt><dd className="mt-1 text-gray-700">{document.quality_score == null ? '—' : `${Math.round(document.quality_score * 100)}%`}</dd></div>
        <div><dt className="text-xs text-gray-600">Embedding</dt><dd className="mt-1 text-gray-700">{document.chunks == null || !document.indexed ? '—' : `${document.chunks} đoạn`}</dd></div>
        <div><dt className="text-xs text-gray-600">Ngày nạp</dt><dd className="mt-1 text-gray-700">{formatDate(document.fetched_at)}</dd></div>
      </dl>
    </article>)}
  </div>;
}

export default function KnowledgeDocumentsPage() {
  const [catalogue, setCatalogue] = useState({ documents: [], summary: {} });
  const [candidates, setCandidates] = useState([]);
  const [status, setStatus] = useState('approved');
  const [query, setQuery] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [knowledgeStatus, setKnowledgeStatus] = useState({});
  const [searchQuestion, setSearchQuestion] = useState('');
  const [searchKeywords, setSearchKeywords] = useState([]);
  const [discoveryJob, setDiscoveryJob] = useState(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [candidateBusy, setCandidateBusy] = useState(null);
  const [candidateNotice, setCandidateNotice] = useState('');
  const [candidateError, setCandidateError] = useState('');

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

  useEffect(() => {
    let active = true;
    if (typeof aiApi.getKnowledgeSourceCandidates !== 'function') return () => { active = false; };
    aiApi.getKnowledgeSourceCandidates({ status: 'pending' })
      .then((data) => { if (active) setCandidates(Array.isArray(data?.candidates) ? data.candidates : []); })
      .catch(() => { if (active) setCandidates([]); });
    return () => { active = false; };
  }, [refreshKey]);

  useEffect(() => {
    let active = true;
    if (typeof aiApi.getKnowledgeStatus !== 'function') return () => { active = false; };
    aiApi.getKnowledgeStatus()
      .then((data) => {
        if (!active) return;
        const latest = data?.latest_query_discovery || null;
        setKnowledgeStatus(data || {});
        if (latest) {
          setDiscoveryJob(latest);
          setSearchKeywords(Array.isArray(latest.keywords) ? latest.keywords : []);
          setSearchQuestion((value) => value || latest.question || '');
        }
      })
      .catch(() => { if (active) setKnowledgeStatus({}); });
    return () => { active = false; };
  }, [refreshKey]);

  useEffect(() => {
    if (!discoveryJob?.job_id || !['queued', 'running'].includes(discoveryJob.status)) return undefined;
    if (typeof aiApi.getKnowledgeDiscovery !== 'function') return undefined;
    let active = true;
    const timer = setInterval(() => {
      aiApi.getKnowledgeDiscovery(discoveryJob.job_id)
        .then((data) => {
          if (!active) return;
          const next = data?.job || data;
          if (!next) return;
          setDiscoveryJob(next);
          setSearchKeywords(Array.isArray(next.keywords) ? next.keywords : []);
          if (!['queued', 'running'].includes(next.status)) setRefreshKey((value) => value + 1);
        })
        .catch(() => { /* keep the last visible progress; the next poll retries */ });
    }, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [discoveryJob?.job_id, discoveryJob?.status]);

  const startSearch = async (event) => {
    event.preventDefault();
    const question = searchQuestion.trim();
    if (!question || searchBusy || typeof aiApi.startKnowledgeDiscovery !== 'function') return;
    setSearchBusy(true);
    setSearchError('');
    try {
      const data = await aiApi.startKnowledgeDiscovery({ question });
      const job = data?.job || data;
      setDiscoveryJob(job || null);
      setSearchKeywords(Array.isArray(job?.keywords) ? job.keywords : []);
      if (job?.question) setSearchQuestion(job.question);
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setSearchError(err.message || 'Không thể bắt đầu tìm nguồn.');
    } finally {
      setSearchBusy(false);
    }
  };

  const reviewCandidate = async (candidate, decision) => {
    const action = decision === 'approve'
      ? aiApi.approveKnowledgeSourceCandidate
      : aiApi.rejectKnowledgeSourceCandidate;
    if (typeof action !== 'function' || candidateBusy) return;

    setCandidateBusy(`${candidate.id}:${decision}`);
    setCandidateNotice('');
    setCandidateError('');
    try {
      await action(candidate.id);
      setCandidates((current) => current.filter((item) => item.id !== candidate.id));
      setCandidateNotice(decision === 'approve'
        ? 'Đã duyệt nguồn. Nguồn sẽ được dùng ở lượt nạp kiến thức kế tiếp.'
        : 'Đã từ chối nguồn và giữ lại trong lịch sử kiểm tra.');
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setCandidateError(err.message || 'Không cập nhật được trạng thái nguồn. Tài khoản cần quyền quản trị.');
    } finally {
      setCandidateBusy(null);
    }
  };

  const summary = catalogue.summary || {};
  const newCount = catalogue.documents.filter((document) => document.is_new).length;
  const latestJob = discoveryJob || knowledgeStatus.latest_query_discovery;
  const discoveryLabel = latestJob
    ? (discoveryStatusLabels[latestJob.status] || latestJob.message || 'Đang cập nhật tác vụ tìm nguồn.')
    : 'Nhập câu hỏi để tách chủ đề và tìm nguồn ngay.';

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

    <section aria-labelledby="need-search-heading" className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Tìm ngay</p>
          <h2 id="need-search-heading" className="mt-1 text-xl font-semibold text-gray-900">Cần tìm</h2>
          <p className="mt-1 max-w-2xl text-sm text-gray-600">Chủ đề được tách từ câu hỏi. Tác vụ chỉ lấy nguồn được phép, kiểm tra nội dung và embedding trước khi áp dụng vào kho chính.</p>
        </div>
        {latestJob?.created_at && <span className="shrink-0 text-xs text-gray-500">Cập nhật {formatDate(latestJob.created_at)}</span>}
      </div>

      <form onSubmit={startSearch} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="knowledge-search-topic">Chủ đề cần tìm</label>
        <input
          id="knowledge-search-topic"
          aria-label="Chủ đề cần tìm"
          value={searchQuestion}
          onChange={(event) => setSearchQuestion(event.target.value)}
          placeholder="Ví dụ: kỹ thuật trồng nho ngón tay tại Đà Nẵng"
          className="min-w-0 flex-1 rounded-xl border border-emerald-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
        />
        <button
          type="submit"
          disabled={searchBusy || !searchQuestion.trim() || typeof aiApi.startKnowledgeDiscovery !== 'function'}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-700 px-5 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Search size={16} aria-hidden="true" />{searchBusy ? 'Đang gửi…' : 'Tìm'}
        </button>
      </form>

      <div className="mt-3 flex min-h-7 flex-wrap items-center gap-2" aria-live="polite">
        {searchKeywords.length > 0
          ? searchKeywords.map((keyword) => <span key={keyword} className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-medium text-emerald-800">{keyword}</span>)
          : <span className="text-xs text-gray-500">Chưa có từ khóa. Hãy nhập câu hỏi rồi bấm Tìm.</span>}
      </div>

      {latestJob && <div className="mt-4 rounded-xl border border-white/80 bg-white p-3">
        <p className="text-sm font-semibold text-gray-900">{discoveryLabel}</p>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-600">
          <span>Kiểm tra: <strong className="text-gray-800">{verificationLabels[latestJob.verification_status] || '—'}</strong></span>
          <span>Kho chính: <strong className="text-gray-800">{applyLabels[latestJob.apply_status] || '—'}</strong></span>
          <span>Nguồn tìm thấy: <strong className="text-gray-800">{latestJob.candidates_found == null ? '—' : latestJob.candidates_found}</strong></span>
          <span>Đã kiểm tra: <strong className="text-gray-800">{latestJob.documents_processed == null ? '—' : latestJob.documents_processed}</strong></span>
          <span>Tài liệu đạt: <strong className="text-gray-800">{latestJob.documents_indexed == null ? '—' : latestJob.documents_indexed}</strong></span>
        </div>
        {latestJob.error && <p className="mt-2 whitespace-pre-line text-xs text-red-700">{latestJob.error}</p>}
      </div>}
      {searchError && <p role="alert" className="mt-3 text-sm text-red-700">{searchError}</p>}
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

    {candidates.length > 0 && <section className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-semibold text-gray-900">Nguồn mới đang chờ kiểm tra</h2>
          <p className="text-sm text-gray-600">Được phát hiện từ registry, tìm kiếm web riêng hoặc danh mục theo chủ đề; nguồn mới vẫn chờ duyệt. Chỉ tài khoản quản trị mới có thể duyệt.</p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-amber-800">{candidates.length} nguồn</span>
      </div>
      <ul className="mt-3 grid gap-2 md:grid-cols-2">
        {candidates.map((candidate) => <li key={candidate.id} className="min-w-0 rounded-xl border border-amber-100 bg-white p-3">
          <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1">
              <a href={candidate.url} target="_blank" rel="noreferrer" className="block truncate font-medium text-emerald-800 hover:underline">{candidate.name || candidate.domain}</a>
              <p className="mt-1 truncate text-xs text-gray-500">{candidate.domain || '—'} · Từ {candidate.discovered_from || 'nguồn đã cấu hình'}</p>
              <p className="mt-2 text-xs text-gray-600">Nguồn này cần được kiểm tra trước khi đưa vào kho chính.</p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
              <button
                type="button"
                aria-label="Duyệt nguồn"
                onClick={() => reviewCandidate(candidate, 'approve')}
                disabled={candidateBusy !== null}
                className="inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {candidateBusy === `${candidate.id}:approve` ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}
                {candidateBusy === `${candidate.id}:approve` ? 'Đang duyệt…' : 'Duyệt nguồn'}
              </button>
              <button
                type="button"
                aria-label="Từ chối nguồn"
                onClick={() => reviewCandidate(candidate, 'reject')}
                disabled={candidateBusy !== null}
                className="inline-flex items-center justify-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {candidateBusy === `${candidate.id}:reject` ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <X size={14} aria-hidden="true" />}
                {candidateBusy === `${candidate.id}:reject` ? 'Đang xử lý…' : 'Từ chối nguồn'}
              </button>
            </div>
          </div>
        </li>)}
      </ul>
    </section>}
    {(candidateNotice || candidateError) && <div className="space-y-2">
      {candidateNotice && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{candidateNotice}</p>}
      {candidateError && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{candidateError}</p>}
    </div>}

    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {loading && !catalogue.documents.length
      ? <div role="status" className="rounded-2xl border bg-white p-10 text-center text-gray-600">Đang tải danh sách tài liệu…</div>
      : <KnowledgeDocumentsTable documents={catalogue.documents} />}
  </div>;
}
