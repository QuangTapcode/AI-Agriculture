import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from 'chart.js';
import {
  CheckCircle,
  Clock,
  DollarSign,
  Download,
  FileText,
  Filter,
  MoreVertical,
  Package,
  TrendingUp,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { EmptyState, InlineLoading, PageError } from '../components/StatusState';
import { useAuth } from '../contexts/AuthContext';
import { getApiErrorMessage } from '../services/api';
import { reportsApi } from '../services/reportsApi';
import { MISSING, hasValue } from '../utils/format';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

/** Thiếu số liệu thì trả em dash; số 0 thật vẫn hiện là 0. */
const formatCurrency = (value) =>
  hasValue(value) ? `${Number(value).toLocaleString('vi-VN')} đ` : MISSING;

const formatQuantity = (value) =>
  hasValue(value) ? `${Number(value).toLocaleString('vi-VN')} kg` : MISSING;

const formatDate = (value) => {
  if (!value) return 'Chưa cập nhật';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('vi-VN');
};

const gradeLabel = (grade) => {
  const labels = {
    grade_1: 'Loại 1',
    grade_2: 'Loại 2',
    grade_3: 'Loại 3',
  };
  return labels[grade] || grade || 'Chưa có';
};

const monthKey = (value) => {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return 'Không rõ';
  return `T${date.getMonth() + 1}`;
};

const ReportsPage = () => {
  const { user } = useAuth();
  const [timeFilter, setTimeFilter] = useState('month');
  const [exportFormat, setExportFormat] = useState('csv');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reportData, setReportData] = useState({
    harvest: [],
    market: [],
    quality: [],
  });
  // Khởi tạo rỗng chứ không phải 0: chưa tải xong thì chưa biết con số nào.
  const [summary, setSummary] = useState({
    total_revenue: null,
    total_quantity: null,
    quality_summary: {},
    top_quality_grade: null,
    monthly_revenue: [],
    record_counts: null,
  });

  const loadReports = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await reportsApi.getSummary(100);

      setReportData({
        quality: data.quality || [],
        harvest: data.harvest || [],
        market: data.market || [],
      });
      setSummary(data || {});
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể tải báo cáo của tài khoản'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [user?.id]);

  const totalRevenue = useMemo(
    () => (hasValue(summary.total_revenue) ? Number(summary.total_revenue) : null),
    [summary.total_revenue]
  );

  const totalQuantity = useMemo(
    () => (hasValue(summary.total_quantity) ? Number(summary.total_quantity) : null),
    [summary.total_quantity]
  );

  const qualitySummary = useMemo(() => {
    if (summary.top_quality_grade) return gradeLabel(summary.top_quality_grade);
    if (!reportData.quality.length) return 'Chưa có';
    const counts = reportData.quality.reduce((result, item) => {
      const label = gradeLabel(item.quality_grade);
      result[label] = (result[label] || 0) + 1;
      return result;
    }, {});
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
  }, [reportData.quality, summary.top_quality_grade]);

  const tableRows = useMemo(() => {
    const marketRows = reportData.market.map((item) => ({
      id: `market-${item.suggestion_id}`,
      date: formatDate(item.created_at),
      crop: item.crop_name || 'Nông sản',
      grade: gradeLabel(item.quality_grade),
      gradeColor: 'bg-green-100 text-green-700',
      price: Number(item.estimated_profit || 0),
      quantity: Number(item.quantity || 0),
      status: item.recommended_channel || 'Gợi ý thị trường',
      statusColor: 'text-green-600',
      statusIcon: <CheckCircle className="h-4 w-4" />,
    }));

    const qualityRows = reportData.quality.map((item) => ({
      id: `quality-${item.record_id}`,
      date: formatDate(item.checked_at),
      crop: item.crop_name || 'Nông sản',
      grade: gradeLabel(item.quality_grade),
      gradeColor: item.quality_grade === 'grade_1' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700',
      price: Number(item.suggested_price || 0),
      quantity: 0,
      status: 'Kiểm định chất lượng',
      statusColor: 'text-yellow-600',
      statusIcon: <Clock className="h-4 w-4" />,
    }));

    const harvestRows = reportData.harvest.map((item) => ({
      id: `harvest-${item.forecast_id}`,
      date: formatDate(item.generated_at),
      crop: item.crop_name || 'Nông sản',
      grade: 'Dự báo',
      gradeColor: 'bg-blue-100 text-blue-700',
      price: 0,
      quantity: 0,
      status: `Thu hoạch ${formatDate(item.expected_harvest_date)}`,
      statusColor: 'text-blue-600',
      statusIcon: <Clock className="h-4 w-4" />,
    }));

    return [...marketRows, ...qualityRows, ...harvestRows];
  }, [reportData]);

  const chartData = useMemo(() => {
    const monthlyRevenue = summary.monthly_revenue || [];
    const labels = monthlyRevenue.map((item) => item.month);

    return {
      labels: labels.length ? labels : ['Chưa có dữ liệu'],
      datasets: [
        {
          label: 'Doanh thu theo tài khoản',
          data: labels.length ? monthlyRevenue.map((item) => Number(item.revenue || 0)) : [0],
          backgroundColor: '#15803d',
          borderRadius: 8,
          barThickness: 56,
        },
      ],
    };
  }, [summary.monthly_revenue]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        padding: 12,
        callbacks: {
          label: (context) => `${context.dataset.label}: ${formatCurrency(context.parsed.y)}`,
        },
      },
    },
    scales: {
      x: { grid: { display: false } },
      y: {
        grid: { color: 'rgba(0, 0, 0, 0.05)' },
        ticks: {
          callback: (value) => `${Number(value).toLocaleString('vi-VN')} đ`,
        },
      },
    },
  };

  const summaryCards = [
    {
      icon: <DollarSign className="h-6 w-6 text-green-600" />,
      label: 'Tổng doanh thu theo tài khoản',
      testId: 'report-total-revenue',
      value: formatCurrency(totalRevenue),
      subtitle: `${reportData.market.length} bản ghi gợi ý thị trường`,
      bgColor: 'bg-green-50',
    },
    {
      icon: <Package className="h-6 w-6 text-yellow-600" />,
      label: 'Chất lượng thường gặp',
      testId: 'report-top-quality',
      value: qualitySummary,
      subtitle: `${reportData.quality.length} đợt kiểm định`,
      bgColor: 'bg-yellow-50',
    },
    {
      icon: <TrendingUp className="h-6 w-6 text-red-600" />,
      label: 'Sản lượng đã ghi nhận',
      testId: 'report-total-quantity',
      value: formatQuantity(totalQuantity),
      subtitle: `${reportData.harvest.length} dự báo thu hoạch`,
      bgColor: 'bg-red-50',
    },
  ];

  const handleExport = (format) => {
    setExportFormat(format);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Báo cáo chi tiết</h1>
          <p className="mt-2 text-gray-600">
            Dữ liệu báo cáo của {user?.name || 'tài khoản đang đăng nhập'}
            {user?.region ? ` tại ${user.region}` : ''}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 hover:bg-gray-50">
            <Filter className="h-4 w-4" />
            <span className="text-sm">Lọc</span>
          </button>
        </div>
      </div>

      {loading && <InlineLoading text="Đang tải báo cáo theo tài khoản..." />}
      {error && <PageError message={error} onRetry={loadReports} />}

      {!loading && !error && (
        <>
          <div className="grid gap-6 md:grid-cols-3">
            {summaryCards.map((card) => (
              <div key={card.label} className={`${card.bgColor} rounded-lg border border-gray-200 p-6`}>
                <div className="mb-4 flex items-start justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/70">
                    {card.icon}
                  </div>
                </div>
                <div className="text-sm font-medium uppercase text-gray-600">{card.label}</div>
                <div data-testid={card.testId} className="mt-2 text-3xl font-bold text-gray-900">
                  {card.value}
                </div>
                <div className="mt-2 text-sm text-gray-600">{card.subtitle}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Doanh thu theo tháng</h2>
                    <p className="mt-1 text-sm text-gray-500">Tổng hợp từ lịch sử gợi ý thị trường của tài khoản.</p>
                  </div>
                  <div className="flex items-center rounded-lg bg-gray-100 p-1">
                    {[
                      ['week', 'Tuần'],
                      ['month', 'Tháng'],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setTimeFilter(value)}
                        className={`rounded-md px-4 py-2 text-sm font-medium ${
                          timeFilter === value ? 'bg-green-700 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="h-80">
                  <Bar data={chartData} options={chartOptions} />
                </div>
              </section>

              <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Lịch sử theo tài khoản</h2>
                    <p className="mt-1 text-sm text-gray-600">Không dùng dữ liệu mẫu phía FE.</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {['csv', 'excel', 'pdf'].map((format) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => handleExport(format)}
                        className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${
                          exportFormat === format
                            ? 'bg-green-700 text-white'
                            : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        {format === 'pdf' ? <Download className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                        <span>{format.toUpperCase()}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {tableRows.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-200">
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Ngày</th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Nông sản</th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Phân loại</th>
                          <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Giá trị</th>
                          <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">Số lượng</th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">Trạng thái</th>
                          <th className="px-4 py-3 text-center text-xs font-medium uppercase text-gray-500">Hành động</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tableRows.map((record) => (
                          <tr key={record.id} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-4 text-sm text-gray-900">{record.date}</td>
                            <td className="px-4 py-4 text-sm font-medium text-gray-900">{record.crop}</td>
                            <td className="px-4 py-4">
                              <span className={`${record.gradeColor} rounded-full px-3 py-1 text-xs font-bold`}>
                                {record.grade}
                              </span>
                            </td>
                            <td className="px-4 py-4 text-right text-sm font-semibold text-gray-900">
                              {record.price ? formatCurrency(record.price) : '-'}
                            </td>
                            <td className="px-4 py-4 text-right text-sm text-gray-900">
                              {record.quantity ? record.quantity.toLocaleString('vi-VN') : '-'}
                            </td>
                            <td className="px-4 py-4">
                              <div className={`flex items-center gap-2 ${record.statusColor}`}>
                                {record.statusIcon}
                                <span className="text-sm font-medium">{record.status}</span>
                              </div>
                            </td>
                            <td className="px-4 py-4 text-center">
                              <button className="text-gray-400 hover:text-gray-600" type="button">
                                <MoreVertical className="h-5 w-5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState
                    title="Chưa có báo cáo cho tài khoản này"
                    description="Các bản ghi kiểm định, dự báo và gợi ý thị trường sẽ xuất hiện sau khi bạn sử dụng các chức năng tương ứng."
                  />
                )}
              </section>
            </div>

            <aside className="space-y-6">
              <section className="rounded-lg border border-green-200 bg-green-50 p-6">
                <h3 className="font-bold text-gray-900">Phân tích theo tài khoản</h3>
                <p className="mt-3 text-sm leading-6 text-gray-700">
                  {tableRows.length
                    ? `Đã tổng hợp ${tableRows.length} bản ghi của ${user?.name || 'người dùng hiện tại'}.`
                    : 'Tài khoản này chưa có dữ liệu để phân tích.'}
                </p>
              </section>
            </aside>
          </div>
        </>
      )}
    </div>
  );
};

export default ReportsPage;
