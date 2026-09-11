import { CircleSlash2 } from 'lucide-react';

export function EmptyState({ title, description, action, icon: Icon = CircleSlash2, dark = false, className = '' }) {
  return (
    <section className={`relative overflow-hidden rounded-[2rem] border p-7 sm:p-10 ${dark ? 'border-white/10 bg-white/[0.045] text-white' : 'border-slate-200 bg-white text-slate-950'} ${className}`}>
      <div aria-hidden="true" className={`absolute -right-12 -top-12 h-40 w-40 rounded-full blur-3xl ${dark ? 'bg-lime-300/10' : 'bg-emerald-100'}`} />
      <div className={`relative grid h-12 w-12 place-items-center rounded-2xl ${dark ? 'bg-lime-300/10 text-lime-300' : 'bg-emerald-50 text-emerald-700'}`}>
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>
      <h2 className="relative mt-6 font-display text-2xl font-bold tracking-tight">{title}</h2>
      <p className={`relative mt-3 max-w-xl leading-7 ${dark ? 'text-slate-300' : 'text-slate-600'}`}>{description}</p>
      {action ? <div className="relative mt-6">{action}</div> : null}
    </section>
  );
}

export default EmptyState;
