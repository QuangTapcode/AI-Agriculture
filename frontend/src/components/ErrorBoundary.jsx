import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
          <div className="max-w-md rounded-lg border border-red-200 bg-white p-6 text-center shadow">
            <div className="mb-3 text-4xl">⚠️</div>
            <h2 className="mb-2 text-lg font-semibold text-gray-800">
              Có lỗi xảy ra
            </h2>
            <p className="mb-4 text-sm text-gray-500">
              {this.state.error?.message || 'Lỗi không xác định. Vui lòng tải lại trang.'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700"
            >
              Tải lại trang
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
