export function FilterBar({ children, className = '', label = 'Bộ lọc' }) {
  return (
    <section aria-label={label} className={`flex min-w-0 flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm ${className}`}>
      {children}
    </section>
  );
}

export function FilterButton({ active = false, children, className = '', ...props }) {
  return (
    <button
      type="button"
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 ${active ? 'bg-emerald-700 text-white' : 'text-slate-600 hover:bg-emerald-50 hover:text-emerald-800'} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
