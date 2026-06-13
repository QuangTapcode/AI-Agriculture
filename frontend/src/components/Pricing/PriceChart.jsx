import { Line } from 'react-chartjs-2';
import { translateUiText } from '../../utils/vietnameseText';

const PriceChart = ({ forecast, days }) => {
  const forecastData = Array.isArray(forecast?.forecast_data) ? forecast.forecast_data : [];
  if (forecastData.length === 0) {
    return null;
  }

  const formatUtcDateLabel = (dateValue) => {
    const date = new Date(dateValue);
    return `${date.getUTCDate()}/${date.getUTCMonth() + 1}`;
  };

  const chartData = {
    labels: forecastData.map((d) => formatUtcDateLabel(d.date)),
    datasets: [
      {
        label: 'Giá dự báo',
        data: forecastData.map((d) => d.predicted_price),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Khoảng tin cậy trên',
        data: forecast.forecast_data.map((d) => d.confidence_upper),
        borderColor: 'rgba(34, 197, 94, 0.3)',
        borderDash: [5, 5],
        fill: false,
        pointRadius: 0,
      },
      {
        label: 'Khoảng tin cậy dưới',
        data: forecast.forecast_data.map((d) => d.confidence_lower),
        borderColor: 'rgba(34, 197, 94, 0.3)',
        borderDash: [5, 5],
        fill: false,
        pointRadius: 0,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: `Dự báo giá ${days} ngày tới`,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          callback: (value) => `${value.toLocaleString()} đ`,
        },
      },
    },
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <div style={{ height: '400px' }}>
        <Line data={chartData} options={chartOptions} />
      </div>

      {forecast.recommendation && (
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm font-medium text-blue-900 mb-2">
            Khuyến nghị:
          </p>
          <p className="text-blue-800">{translateUiText(forecast.recommendation)}</p>
        </div>
      )}
    </div>
  );
};

export default PriceChart;
