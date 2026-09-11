export function PageHeader({ title, description, action, context, dark = false, className = '' }) {
  return (
    <header className={`flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between ${className}`}>
      <div className="max-w-3xl">
        {context ? <p className={`text-sm font-semibold ${dark ? 'text-lime-300' : 'text-emerald-700'}`}>{context}</p> : null}
        <h1 className={`mt-2 font-display text-3xl font-extrabold tracking-[-0.035em] sm:text-4xl lg:text-5xl ${dark ? 'text-white' : 'text-slate-950'}`}>
          {title}
        </h1>
        {description ? <p className={`mt-3 max-w-2xl text-base leading-7 ${dark ? 'text-slate-300' : 'text-slate-600'}`}>{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

export default PageHeader;
