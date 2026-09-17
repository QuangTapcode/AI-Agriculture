import { AlertTriangle, Clock3, Database, Radio } from 'lucide-react';
import { normalizeDataMeta } from '../../utils/dataTrust';

const STYLE = {
  live: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  cached: 'border-amber-200 bg-amber-50 text-amber-700',
  database: 'border-sky-200 bg-sky-50 text-sky-700',
  unavailable: 'border-slate-200 bg-slate-100 text-slate-700',
};

const ICON = {
  live: Radio,
  cached: Clock3,
  database: Database,
  unavailable: AlertTriangle,
};

const STATUS_LABEL = {
  live: 'Trực tiếp',
  cached: 'Bản lưu',
  database: 'Cơ sở dữ liệu',
  unavailable: 'Chưa có dữ liệu',
};

export function SourceBadge({ metadata = {}, className = '', showTime = false }) {
  const meta = normalizeDataMeta(metadata);
  const Icon = ICON[meta.status];
  const source = meta.sourceName || STATUS_LABEL[meta.status];
  const time = meta.updatedAt ? new Date(meta.updatedAt).toLocaleString('vi-VN') : '';

  return (
    <span
      className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${STYLE[meta.status]} ${className}`}
      title={time ? `${source} · Cập nhật ${time}` : source}
    >
      <Icon aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate">{source}</span>
      {showTime && time ? <span className="hidden opacity-70 sm:inline">· {time}</span> : null}
    </span>
  );
}

export default SourceBadge;
