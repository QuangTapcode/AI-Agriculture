import { CheckCircle2, TriangleAlert, X } from 'lucide-react';

export function Toast({ open, tone = 'success', title, message, onClose }) {
  const Icon = tone === 'success' ? CheckCircle2 : TriangleAlert;
  return (
    <div role="status" aria-live="polite" className={`fixed bottom-5 right-5 z-[80] w-[calc(100%-2.5rem)] max-w-sm transition-all duration-300 ${open ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-4 opacity-0'}`}>
      <div className="rounded-2xl border border-white/10 bg-[#0b1d16] p-4 text-white shadow-2xl shadow-black/30">
        <div className="flex items-start gap-3">
          <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${tone === 'success' ? 'text-lime-300' : 'text-rose-300'}`} />
          <div className="min-w-0 flex-1"><p className="font-semibold">{title}</p>{message ? <p className="mt-1 text-sm text-slate-300">{message}</p> : null}</div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Đóng thông báo"><X className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );
}

export default Toast;
