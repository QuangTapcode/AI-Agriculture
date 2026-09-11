import { Clock3, Database, Radio, TriangleAlert } from 'lucide-react';
import { normalizeDataMeta } from '../../utils/dataTrust';

const STYLE = {
  live: 'border-lime-300/30 bg-lime-300/10 text-lime-100',
  cached: 'border-amber-300/30 bg-amber-300/10 text-amber-100',
  database: 'border-sky-300/30 bg-sky-300/10 text-sky-100',
  unavailable: 'border-slate-400/30 bg-slate-400/10 text-slate-300',
};

const ICON = {
  live: Radio,
  cached: Clock3,
  database: Database,
  unavailable: TriangleAlert,
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
