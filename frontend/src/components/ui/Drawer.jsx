import { useEffect } from 'react';
import { X } from 'lucide-react';

export function Drawer({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (event) => event.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  return (
    <div className={`fixed inset-0 z-[70] ${open ? 'pointer-events-auto' : 'pointer-events-none'}`} aria-hidden={!open}>
      <button type="button" aria-label="Đóng" onClick={onClose} className={`absolute inset-0 bg-slate-950/55 backdrop-blur-sm transition-opacity ${open ? 'opacity-100' : 'opacity-0'}`} />
      <section role="dialog" aria-modal="true" aria-label={title} className={`absolute inset-y-0 right-0 w-full max-w-lg bg-white p-6 shadow-2xl transition-transform duration-300 ${open ? 'translate-x-0' : 'translate-x-full'}`}>
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 pb-4">
          <h2 className="font-display text-xl font-bold text-slate-950">{title}</h2>
          <button type="button" onClick={onClose} className="grid h-10 w-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100" aria-label="Đóng bảng chi tiết"><X className="h-5 w-5" /></button>
        </header>
        <div className="h-[calc(100%-4rem)] overflow-y-auto py-5">{children}</div>
      </section>
    </div>
  );
}

export default Drawer;
