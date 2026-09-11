import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import { getTrustedMetric } from '../../utils/dataTrust';
import SourceBadge from './SourceBadge';

const TREND = {
  up: { Icon: ArrowUpRight, label: 'Tăng', className: 'text-lime-300' },
  down: { Icon: ArrowDownRight, label: 'Giảm', className: 'text-rose-300' },
  stable: { Icon: Minus, label: 'Ổn định', className: 'text-slate-300' },
};

export function MetricCard({
  label,
  value,
  unit,
  metadata = {},
  formatter = (item) => String(item),
  trend,
  icon: Icon,
  className = '',
}) {
  const metric = getTrustedMetric(value, metadata);
  const trendMeta = trend ? TREND[trend] : null;

  return (
    <article className={`field-panel group min-w-0 p-5 sm:p-6 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm font-semibold text-slate-300">{label}</p>
        {Icon ? (
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-lime-300/10 text-lime-300 transition-transform duration-300 group-hover:-translate-y-1">
            <Icon aria-hidden="true" className="h-5 w-5" />
          </span>
        ) : null}
      </div>

      <div className="mt-5 flex min-h-12 items-end gap-2">
        <strong className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
          {metric.available ? formatter(metric.value) : '—'}
        </strong>
        {metric.available && unit ? <span className="pb-1 text-sm text-slate-400">{unit}</span> : null}
      </div>

      <div className="mt-5 flex min-w-0 flex-wrap items-center gap-2">
        <SourceBadge metadata={metric.meta} />
        {metric.available && trendMeta ? (
          <span className={`inline-flex items-center gap-1 text-xs font-semibold ${trendMeta.className}`}>
            <trendMeta.Icon aria-hidden="true" className="h-3.5 w-3.5" />
            {trendMeta.label}
          </span>
        ) : null}
      </div>

      {!metric.available ? <p className="mt-3 text-sm text-slate-400">{metric.reason}</p> : null}
    </article>
  );
}

export default MetricCard;
