import { BookOpen, Bot, Check, Copy, FileText, Loader2, Menu, Plus, Search, Send, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { aiApi } from '../services/aiApi';
import { formatNumber } from '../utils/format';

const suggestions = ['Kỹ thuật trồng cà phê vụ mới', 'Cách nhận biết sâu cuốn lá lúa', 'Giá sầu riêng tại Đắk Lắk hôm nay', 'Lịch bón phân theo tài liệu của tôi'];
const ragLabels = {
  ready: 'Đã tìm thấy tài liệu tham khảo', empty: 'Kho tài liệu trống — chưa có nguồn tài liệu để đối chiếu.',
  no_match: 'Chưa tìm thấy đoạn tài liệu phù hợp với câu hỏi này.',
  unavailable: 'Tra cứu tài liệu tạm gián đoạn. Câu trả lời chưa được đối chiếu với kho tài liệu.',
  disabled: 'Tra cứu tài liệu đang tắt.', sign_in_required: 'Đăng nhập để nạp và tra cứu tài liệu của bạn.',
};
const runLabels = {
  success: 'Thành công', partial_success: 'Hoàn tất một phần', failed: 'Thất bại', running: 'Đang chạy',
};
const dateLabel = (value) => {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return 'Hôm nay';
  if (date.toDateString() === yesterday.toDateString()) return 'Hôm qua';
  return date.toLocaleDateString('vi-VN');
};
const timeLabel = (value) => new Date(value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
const fromTurns = (turns) => turns.flatMap((turn) => [
  { id: `${turn.id}-user`, role: 'user', content: turn.user_message, createdAt: turn.created_at },
  { id: `${turn.id}-bot`, role: 'assistant', content: turn.ai_response, createdAt: turn.created_at, rag: turn.rag },
]);

export function Sources({ rag }) {
  if (!rag || rag.status === 'not_used') return null;
  return <div className="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-600">
    <p>{ragLabels[rag.status]}</p>
    {rag.sources?.map((source) => <details key={source.citation} className="mt-2 rounded-lg bg-green-50 p-2 text-gray-700">
      <summary className="cursor-pointer break-words font-medium text-green-800 [overflow-wrap:anywhere]">[{source.citation}] {source.source_name || source.name} · Trang {source.page}</summary>
      <p className="mt-2 whitespace-pre-wrap break-words leading-5 [overflow-wrap:anywhere]">{source.excerpt}</p>
      {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block break-all font-medium text-green-800 underline">Mở tài liệu gốc</a>}
    </details>)}
  </div>;
}

export default function AIChatPage() {
  const { isAuthenticated, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(false);
  const [history, setHistory] = useState([]);
  const [query, setQuery] = useState('');
  const [historyLoading, setHistoryLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [knowledgeStatus, setKnowledgeStatus] = useState(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [copied, setCopied] = useState(null);
  const endRef = useRef(null);
  const fileRef = useRef(null);
  const epoch = useRef(0);
  const historyRequest = useRef(0);
  const locked = busy || opening || deleting || uploading || Boolean(confirmDelete);

  const loadHistory = useCallback(async (offset = 0) => {
    if (!isAuthenticated) return;
    const request = ++historyRequest.current;
    const version = epoch.current;
    setHistoryLoading(true);
    try {
      const data = await aiApi.getConversations(query, offset);
      if (request !== historyRequest.current || version !== epoch.current) return;
      // Luôn giữ hình dạng mảng: phản hồi thiếu `history` từng làm history.length ném lỗi.
      const incoming = Array.isArray(data?.history) ? data.history : [];
      setHistory((previous) =>
        offset
          ? [...previous, ...incoming.filter((item) => !previous.some((p) => p.id === item.id))]
          : incoming
      );
      setHasMore(Boolean(data?.has_more));
    } catch (err) {
      if (request === historyRequest.current && version === epoch.current) setError(err.message || 'Không tải được lịch sử.');
    } finally {
      if (request === historyRequest.current && version === epoch.current) setHistoryLoading(false);
    }
  }, [isAuthenticated, query]);

  useEffect(() => {
    epoch.current += 1;
    historyRequest.current += 1;
    setHistory([]); setMessages([]); setDocuments([]); setKnowledgeStatus(null); setQuery(''); setInput('');
    setSessionId(crypto.randomUUID()); setError(''); setNotice(''); setBusy(false); setOpening(false);
    setUploading(false); setDeleting(false); setConfirmDelete(null); setHasMore(false); setHistoryLoading(false); setKnowledgeLoading(false);
    return () => { epoch.current += 1; };
  }, [user?.id]);

  useEffect(() => {
    historyRequest.current += 1;
    const timer = setTimeout(() => loadHistory(), 300);
    return () => clearTimeout(timer);
  }, [loadHistory, user?.id]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);

  const newConversation = () => {
    if (locked) return;
    setMessages([]); setSessionId(crypto.randomUUID()); setInput(''); setHistoryOpen(false); setError('');
  };

  const openConversation = async (item) => {
    if (locked) return;
    const version = epoch.current;
    setOpening(true); setError('');
    try {
      let data = await aiApi.getConversation(item.id);
      const id = data.session_id;
      const turns = [...data.turns];
      while (data.has_more && epoch.current === version) {
        data = await aiApi.getConversation(id, turns.length);
        turns.push(...data.turns);
      }
      if (epoch.current !== version) return;
      setMessages(fromTurns(turns)); setSessionId(id); setInput(''); setHistoryOpen(false);
      loadHistory();
    } catch (err) {
      if (epoch.current === version) setError(err.message || 'Không mở được hội thoại.');
    } finally { if (epoch.current === version) setOpening(false); }
  };

  const send = async (event) => {
    event?.preventDefault();
    const question = input.trim();
    if (!question || locked) return;
    const version = epoch.current;
    setInput(''); setBusy(true); setError('');
    setMessages((previous) => [...previous, { id: crypto.randomUUID(), role: 'user', content: question, createdAt: new Date().toISOString() }]);
    try {
      const data = await aiApi.chat({ question, sessionId });
      if (version !== epoch.current) return;
      setMessages((previous) => [...previous, {
        id: crypto.randomUUID(), role: 'assistant', content: data.reply || data.answer,
        createdAt: data.created_at || new Date().toISOString(), rag: data.rag,
      }]);
      if (isAuthenticated && data.history_saved === false) setError('Đã nhận câu trả lời nhưng chưa lưu được lịch sử. Hãy sao chép nội dung cần giữ.');
      loadHistory();
    } catch (err) {
      if (version !== epoch.current) return;
      setMessages((previous) => [...previous, { id: crypto.randomUUID(), role: 'assistant', isError: true,
        content: err.message || 'Trợ lý chưa phản hồi. Hãy thử lại.', retry: question, createdAt: new Date().toISOString() }]);
    } finally { if (version === epoch.current) setBusy(false); }
  };

  const refreshDocuments = async () => {
    if (!isAuthenticated) return;
    const version = epoch.current;
    try {
      const data = await aiApi.getDocuments();
      if (version === epoch.current) setDocuments(Array.isArray(data?.documents) ? data.documents : []);
    } catch (err) { if (version === epoch.current) setError(err.message); }
  };

  const refreshKnowledgeStatus = async () => {
    if (!isAuthenticated) return;
    const version = epoch.current;
    setKnowledgeLoading(true);
    try {
      const data = await aiApi.getKnowledgeStatus();
      if (version === epoch.current) setKnowledgeStatus(data);
    } catch (err) { if (version === epoch.current) setError(err.message); }
    finally { if (version === epoch.current) setKnowledgeLoading(false); }
  };

  const refreshLibrary = () => {
    setError('');
    refreshDocuments();
    refreshKnowledgeStatus();
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setError('Tài liệu tối đa 10 MB.'); return; }
    const version = epoch.current;
    setUploading(true); setError(''); setNotice('');
    try {
      const data = await aiApi.uploadDocument(file);
      if (version !== epoch.current) return;
      setNotice(data.duplicate ? 'Tài liệu này đã có trong kho.' : `Đã nạp ${data.name}: ${data.chunks} đoạn có thể tra cứu.`);
      await refreshDocuments();
    } catch (err) { if (version === epoch.current) setError(err.message); }
    finally { if (version === epoch.current) setUploading(false); }
  };

  const remove = async () => {
    const target = confirmDelete;
    const version = epoch.current;
    setDeleting(true); setError('');
    try {
      if (target.kind === 'all') await aiApi.clearHistory();
      else if (target.kind === 'document') await aiApi.deleteDocument(target.id);
      else await aiApi.deleteConversation(target.id);
      if (version !== epoch.current) return;
      if (target.kind === 'document') await refreshDocuments();
      else {
        if (target.kind === 'all' || target.id === sessionId) { setMessages([]); setSessionId(crypto.randomUUID()); }
        await loadHistory();
      }
      setConfirmDelete(null);
    } catch (err) { if (version === epoch.current) setError(err.message); }
    finally { if (version === epoch.current) setDeleting(false); }
  };

  const sidebar = <>
    <div className="flex items-center justify-between"><h2 className="font-bold">Hội thoại của bạn</h2>
      <button onClick={() => setHistoryOpen(false)} className="p-2 lg:hidden" aria-label="Đóng lịch sử"><X size={18} /></button></div>
    <button disabled={locked} onClick={newConversation} className="my-4 flex w-full items-center justify-center gap-2 rounded-xl bg-green-700 p-3 text-sm font-semibold text-white disabled:opacity-50"><Plus size={18} /> Hội thoại mới</button>
    {isAuthenticated ? <>
      <div className="relative"><Search size={16} className="absolute left-3 top-3 text-gray-600" /><input aria-label="Tìm trong lịch sử chat" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm nội dung hội thoại…" className="w-full rounded-lg border py-2 pl-9 pr-3 text-sm" /></div>
      <div className="my-3 flex justify-between text-xs text-gray-600"><button onClick={() => loadHistory()} disabled={historyLoading}>Tải lại</button><button disabled={locked || !history.length} onClick={() => setConfirmDelete({ kind: 'all' })} className="text-red-600 disabled:opacity-40">Xóa lịch sử</button></div>
      <div className="space-y-2">{history.map((item, index) => <div key={item.id}>
        {(index === 0 || dateLabel(history[index - 1].created_at) !== dateLabel(item.created_at)) && <p className="mb-2 mt-4 text-xs font-semibold text-gray-600">{dateLabel(item.created_at)}</p>}
        <div className={`flex rounded-xl border ${sessionId === item.id ? 'border-green-300 bg-green-50' : 'border-transparent hover:bg-gray-50'}`}>
          <button disabled={locked} onClick={() => openConversation(item)} className="min-w-0 flex-1 p-3 text-left"><p className="truncate text-sm font-semibold">{item.user_message}</p><p className="mt-1 truncate text-xs text-gray-600">{item.ai_response}</p><p className="mt-2 text-xs text-gray-600">{item.turn_count} lượt · {timeLabel(item.created_at)}</p></button>
          <button disabled={locked} onClick={() => setConfirmDelete({ kind: 'conversation', id: item.id })} aria-label={`Xóa hội thoại ${item.user_message}`} className="self-start p-2 text-gray-600 hover:text-red-600"><Trash2 size={15} /></button>
        </div>
      </div>)}</div>
      {historyLoading && <p role="status" className="py-4 text-sm text-gray-600">Đang tải lịch sử…</p>}
      {!historyLoading && !history.length && <p className="py-6 text-sm text-gray-600">{query ? 'Không tìm thấy hội thoại phù hợp.' : 'Hội thoại của bạn sẽ xuất hiện ở đây.'}</p>}
      {hasMore && <button disabled={historyLoading} onClick={() => loadHistory(history.length)} className="mt-4 w-full rounded-lg border p-2 text-sm">Xem thêm</button>}
    </> : <p className="text-sm leading-6 text-gray-600">Đăng nhập để lưu hội thoại, tiếp tục trao đổi và sử dụng kho tài liệu riêng.</p>}
  </>;

  return <div className="flex h-[calc(100dvh-8rem)] min-h-[560px] max-w-full gap-4 overflow-x-hidden">
    <aside className="hidden w-72 shrink-0 overflow-y-auto rounded-2xl border bg-white p-4 lg:block">{sidebar}</aside>
    {historyOpen && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden"><aside className="h-full w-80 max-w-[90vw] overflow-y-auto bg-white p-4">{sidebar}</aside></div>}
    <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border bg-white">
      <header className="flex items-center gap-3 border-b p-4">
        <button onClick={() => setHistoryOpen(true)} aria-label="Mở lịch sử" className="lg:hidden"><Menu size={22} /></button>
        <div className="rounded-xl bg-green-700 p-2 text-white"><Bot size={24} /></div>
        <div className="min-w-0 flex-1"><h1 className="font-bold text-gray-900">Trợ lý nông nghiệp</h1><p className="text-xs text-gray-600">Tra cứu tài liệu · Ghi nhớ hội thoại</p></div>
        <button
          type="button"
          onClick={() => { setLibraryOpen(!libraryOpen); if (!libraryOpen) refreshLibrary(); }}
          aria-label="Kho tài liệu"
          aria-expanded={libraryOpen}
          className="flex min-h-11 items-center gap-2 rounded-lg border p-2 text-sm text-green-800"
        >
          <BookOpen size={18} aria-hidden="true" />
          {/* Chữ ẩn dưới sm nên nút cần aria-label, nếu không nó thành nút không tên. */}
          <span className="hidden sm:inline">Kho tài liệu</span>
        </button>
      </header>
      {error && <div role="alert" className="flex items-center justify-between bg-red-50 px-4 py-2 text-sm text-red-700">{error}<button onClick={() => setError('')} aria-label="Đóng thông báo lỗi"><X size={16} /></button></div>}
      {notice && <div role="status" className="flex items-center justify-between bg-green-50 px-4 py-2 text-sm text-green-800">{notice}<button onClick={() => setNotice('')} aria-label="Đóng thông báo"><X size={16} /></button></div>}
      {libraryOpen && <div className="max-h-96 shrink-0 overflow-y-auto border-b bg-gray-50 p-4">
        <div className="flex items-center justify-between"><h2 className="text-sm font-bold">Kho tài liệu</h2><button onClick={() => setLibraryOpen(false)} aria-label="Đóng kho tài liệu"><X size={18} /></button></div>
        {isAuthenticated && <div className="mt-3 rounded-xl border border-green-200 bg-white p-3 text-xs">
          <div className="flex items-center justify-between gap-3"><h3 className="font-bold text-gray-800">Dữ liệu tự động hằng đêm</h3><button onClick={refreshLibrary} disabled={knowledgeLoading} className="font-medium text-green-800 disabled:opacity-50">Kiểm tra lại</button></div>
          {knowledgeLoading && !knowledgeStatus && <p role="status" className="mt-2 text-gray-600">Đang đọc trạng thái…</p>}
          {knowledgeStatus && <>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-1 font-semibold ${knowledgeStatus.last_run?.status === 'success' ? 'bg-green-100 text-green-800' : knowledgeStatus.last_run?.status === 'partial_success' ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-700'}`}>{runLabels[knowledgeStatus.last_run?.status] || 'Chưa chạy'}</span>
              <span className="text-gray-600">Lịch chạy: {String(knowledgeStatus.schedule_hour).padStart(2, '0')}:00 mỗi ngày</span>
            </div>
            {knowledgeStatus.last_run?.finished_at && <p className="mt-2 text-gray-600">Lần hoàn tất gần nhất: {new Date(knowledgeStatus.last_run.finished_at).toLocaleString('vi-VN')}</p>}
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-lg bg-gray-50 p-2"><strong className="block text-base text-gray-900">{knowledgeStatus.configured_sources}</strong>Nguồn theo dõi</div>
              <div className="rounded-lg bg-gray-50 p-2">
                <strong className="block text-base text-gray-900">
                  {formatNumber(knowledgeStatus.last_run?.records_fetched)}
                </strong>
                Tài liệu phát hiện
              </div>
              <div className="rounded-lg bg-gray-50 p-2">
                <strong className="block text-base text-gray-900">
                  {formatNumber(knowledgeStatus.last_run?.records_saved)}
                </strong>
                Tài liệu mới
              </div>
              <div className="rounded-lg bg-gray-50 p-2"><strong className="block text-base text-gray-900">{knowledgeStatus.indexed_documents ?? '—'}</strong>Đã lập chỉ mục</div>
            </div>
            <p className="mt-2 text-gray-600">{knowledgeStatus.indexed_chunks ?? '—'} đoạn embedding có thể tra cứu.</p>
            <Link to="/knowledge-documents" className="mt-3 inline-flex items-center gap-1 font-semibold text-green-800 hover:underline">Xem tất cả tài liệu đã nạp</Link>
            {knowledgeStatus.last_run?.has_error && <details className="mt-2 rounded-lg bg-amber-50 p-2 text-amber-900"><summary className="cursor-pointer font-medium">Xem nguồn gặp lỗi</summary><p className="mt-2 whitespace-pre-wrap break-words">{knowledgeStatus.last_run.error}</p></details>}
          </>}
        </div>}
        <h3 className="mt-4 text-sm font-bold">Tài liệu của bạn</h3>
        <p className="my-2 text-xs leading-5 text-gray-600">Nạp sách kỹ thuật, hướng dẫn canh tác hoặc dữ liệu mùa vụ để trợ lý tra cứu. PDF có văn bản, TXT, Markdown · tối đa 10 MB/tệp.</p>
        {isAuthenticated ? <>
          <input type="file" ref={fileRef} accept=".pdf,.txt,.md" onChange={upload} className="hidden" />
          <div className="flex gap-3"><button disabled={locked} onClick={() => fileRef.current?.click()} className="rounded-lg bg-green-700 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{uploading ? 'Đang đọc và lập chỉ mục…' : 'Nạp tài liệu'}</button><button onClick={refreshLibrary} className="text-xs text-green-800">Tải lại</button></div>
          {!documents.length && <p className="mt-3 text-xs text-gray-600">Chưa có tài liệu. Thêm tài liệu để bắt đầu đối chiếu nguồn.</p>}
          {documents.map((doc) => <div key={doc.id} className="mt-2 flex items-center gap-2 rounded-lg border bg-white p-2 text-xs"><FileText size={16} className="shrink-0 text-green-700" /><span className="min-w-0 flex-1 truncate">{doc.name} · {doc.chunks} đoạn</span><button disabled={locked} onClick={() => setConfirmDelete({ kind: 'document', id: doc.id })} aria-label={`Xóa tài liệu ${doc.name}`} className="p-1 text-gray-600 hover:text-red-600"><Trash2 size={15} /></button></div>)}
        </> : <p className="text-sm text-gray-600">Đăng nhập để sử dụng kho tài liệu riêng.</p>}
      </div>}
      <div className="flex-1 overflow-y-auto bg-gray-50/60 p-4 sm:p-6" aria-live="polite" aria-busy={busy || opening}>
        {!messages.length && <div className="mx-auto max-w-xl py-10 text-center"><Bot size={44} className="mx-auto mb-4 text-green-700" /><h2 className="text-xl font-bold">Hôm nay bạn cần hỗ trợ gì?</h2><p className="mt-3 text-sm leading-6 text-gray-600">Hãy cho biết cây trồng, khu vực và tình trạng thực tế. Bạn có thể nạp tài liệu để câu trả lời có nguồn tham khảo rõ ràng.</p><div className="mt-6 grid gap-2 sm:grid-cols-2">{suggestions.map((text) => <button key={text} onClick={() => setInput(text)} className="rounded-xl border bg-white p-3 text-left text-sm hover:border-green-500">{text}</button>)}</div></div>}
        {messages.map((message) => <article key={message.id} className={`mb-5 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
          <div className={`min-w-0 max-w-[95%] rounded-2xl p-4 sm:max-w-[85%] ${message.role === 'user' ? 'bg-green-700 text-white' : message.isError ? 'border border-red-200 bg-red-50' : 'border bg-white'}`}>
            {message.role === 'user' ? <p className="whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">{message.content}</p> : <div className="prose prose-sm max-w-none break-words [overflow-wrap:anywhere] prose-a:break-all prose-pre:max-w-full prose-pre:overflow-x-auto"><ReactMarkdown>{message.content}</ReactMarkdown></div>}
            <Sources rag={message.rag} />
            <div className={`mt-2 flex items-center gap-3 text-xs ${message.role === 'user' ? 'text-green-100' : 'text-gray-600'}`}><span>{timeLabel(message.createdAt)}</span>
              {message.role === 'assistant' && <button aria-label="Sao chép câu trả lời" onClick={async () => { try { await navigator.clipboard.writeText(message.content); setCopied(message.id); } catch { setError('Không sao chép được. Hãy chọn văn bản để sao chép.'); } }}>{copied === message.id ? <Check size={14} /> : <Copy size={14} />}</button>}
              {message.isError && <button disabled={locked} onClick={() => setInput(message.retry)} className="text-red-700 underline">Soạn lại câu hỏi</button>}
            </div>
          </div>
        </article>)}
        {(busy || opening) && <div role="status" className="flex items-center gap-2 text-sm text-green-800"><Loader2 size={18} className="animate-spin" />{opening ? 'Đang mở hội thoại…' : 'Đang tra cứu tài liệu và soạn câu trả lời…'}</div>}
        <div ref={endRef} />
      </div>
      <form onSubmit={send} className="border-t p-4"><div className="flex items-end gap-2"><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(); } }} disabled={locked} maxLength={8000} rows={2} placeholder="Nhập câu hỏi…" aria-label="Câu hỏi cho trợ lý" className="min-w-0 flex-1 resize-none rounded-xl border p-3 text-sm outline-none focus:border-green-600" /><button type="submit" disabled={!input.trim() || locked} aria-label="Gửi câu hỏi" className="rounded-xl bg-green-700 p-3 text-white disabled:opacity-40"><Send size={20} /></button></div><p className="mt-2 text-xs text-gray-600">Enter để gửi · Shift+Enter để xuống dòng. Hãy kiểm tra nguồn trước khi áp dụng.</p></form>
    </section>
    {confirmDelete && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><div role="dialog" aria-modal="true" aria-labelledby="delete-title" className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"><h2 id="delete-title" className="font-bold">{confirmDelete.kind === 'all' ? 'Xóa toàn bộ lịch sử?' : confirmDelete.kind === 'document' ? 'Xóa tài liệu khỏi kho tra cứu?' : 'Xóa hội thoại này?'}</h2><p className="mt-2 text-sm text-gray-600">{confirmDelete.kind === 'document' ? 'Các câu trả lời đã lưu vẫn giữ trích dẫn cũ; câu hỏi mới sẽ không tra cứu tài liệu này.' : 'Các lượt trao đổi sẽ được gỡ khỏi lịch sử và bộ nhớ của trợ lý.'}</p><div className="mt-5 flex justify-end gap-2"><button disabled={deleting} onClick={() => setConfirmDelete(null)} className="rounded-lg border px-4 py-2 text-sm">Hủy</button><button autoFocus disabled={deleting} onClick={remove} className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white">{deleting ? 'Đang xóa…' : 'Xóa'}</button></div></div></div>}
  </div>;
}
