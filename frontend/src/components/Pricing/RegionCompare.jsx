import { MapPin, TrendingDown, TrendingUp } from 'lucide-react';

const RegionCompare = ({ data }) => {
  if (!data || !data.regions || data.regions.length === 0) {
    return null;
  }

  const sortedRegions = [...data.regions].sort(
    (a, b) =>
      (Number(String(b.price).replace(/[^\d.-]/g, '')) || 0) -
      (Number(String(a.price).replace(/[^\d.-]/g, '')) || 0)
  );

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold mb-4">So sánh giá các vùng</h2>

      <div className="space-y-3">
        {sortedRegions.map((region, index) => (
          <div
            key={region.region}
            className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
          >
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <MapPin className="h-5 w-5 text-primary-600" />
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-gray-900">
                  {region.region}
                </p>
                <p className="text-xs text-gray-500">{region.date}</p>
              </div>
            </div>

            <div className="text-right">
              <p className="text-lg font-bold text-gray-900">
                {(Number(String(region.price).replace(/[^\d.-]/g, '')) || 0).toLocaleString()} đ/kg
              </p>
              {sortedRegions.length > 1 && index === 0 && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <TrendingUp className="h-3 w-3 mr-1" />
                  Cao nhất
                </span>
              )}
              {sortedRegions.length > 1 && index === sortedRegions.length - 1 && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                  <TrendingDown className="h-3 w-3 mr-1" />
                  Thấp nhất
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RegionCompare;
