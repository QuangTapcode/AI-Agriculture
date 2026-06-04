import React from 'react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import DataSourceBadge from './DataSourceBadge';
import { API_FAILURE_MESSAGE } from '../utils/apiResponse';

export function StatusState({
  status = 'idle',
  title,
  message,
  error,
  source,
  actions,
  onRetry,
  retryLabel = 'Thử lại',
  className = '',
  showSourceBadge = true,
}) {
  const isLoading = status === 'loading';
  const isError = status === 'error';
  const isEmpty = status === 'empty';

  const resolvedTitle =
    title ||
    (isError
      ? 'Không thể tải dữ liệu'
      : isLoading
        ? 'Đang tải dữ liệu'
        : isEmpty
          ? 'Chưa có dữ liệu'
          : 'Hoàn tất');

  const resolvedMessage =
    message ||
    error ||
    (isError
      ? API_FAILURE_MESSAGE
      : isLoading
        ? 'Vui lòng chờ trong giây lát.'
        : isEmpty
          ? 'Hiện chưa có dữ liệu hiển thị.'
          : '');

  const icon = isLoading ? (
    <Loader2 className="h-5 w-5 animate-spin text-sky-600" />
  ) : isError ? (
    <AlertCircle className="h-5 w-5 text-red-600" />
  ) : (
    <RefreshCw className="h-5 w-5 text-slate-500" />
  );

  return (
    <div className={['rounded-2xl border border-slate-200 bg-white p-4 shadow-sm', className].filter(Boolean).join(' ')}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-900">{resolvedTitle}</h3>
            {showSourceBadge && source ? <DataSourceBadge source={source} compact /> : null}
          </div>
          {resolvedMessage ? <p className="mt-1 text-sm text-slate-600">{resolvedMessage}</p> : null}
          {(actions || onRetry) ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {onRetry ? (
                <button
                  type="button"
                  onClick={onRetry}
                  className="inline-flex items-center rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-800"
                >
                  {retryLabel}
                </button>
              ) : null}
              {actions}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, description, source, actions, onRetry, retryLabel, className, showSourceBadge }) {
  return (
    <StatusState
      status="empty"
      title={title}
      message={description}
      source={source}
      actions={actions}
      onRetry={onRetry}
      retryLabel={retryLabel}
      className={className}
      showSourceBadge={showSourceBadge}
    />
  );
}

export function InlineLoading({ text = 'Đang tải dữ liệu...', className = '', source, showSourceBadge = true }) {
  return (
    <StatusState
      status="loading"
      message={text}
      source={source}
      className={className}
      showSourceBadge={showSourceBadge}
    />
  );
}

export function PageError({ message, error, source, onRetry, retryLabel = 'Thử lại', className = '', showSourceBadge = true }) {
  return (
    <StatusState
      status="error"
      message={message}
      error={error}
      source={source}
      onRetry={onRetry}
      retryLabel={retryLabel}
      className={className}
      showSourceBadge={showSourceBadge}
    />
  );
}

export default StatusState;
