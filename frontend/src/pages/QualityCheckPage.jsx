import {
  AlertTriangle,
  Camera,
  CheckCircle,
  FileImage,
  Image as ImageIcon,
  Sparkles,
  Upload,
  XCircle,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getApiErrorMessage } from '../services/api';
import { qualityApi } from '../services/qualityApi';

const gradeMeta = {
  grade_1: {
    label: 'Hạng A',
    description: 'Chất lượng cao',
    icon: CheckCircle,
    color: 'from-green-700 to-green-900',
  },
  grade_2: {
    label: 'Hạng B',
    description: 'Chất lượng trung bình',
    icon: AlertTriangle,
    color: 'from-yellow-600 to-yellow-800',
  },
  grade_3: {
    label: 'Hạng C',
    description: 'Cần xử lý hoặc chế biến',
    icon: XCircle,
    color: 'from-red-700 to-red-900',
  },
};

const QualityCheckPage = () => {
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [cropName, setCropName] = useState('ca chua');
  const [region, setRegion] = useState('Ha Noi');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => () => {
    if (selectedImage) {
      URL.revokeObjectURL(selectedImage);
    }
  }, [selectedImage]);

  const analyzeFile = async (file) => {
    if (!file) return;
    setIsAnalyzing(true);
    setError(null);
    setAnalysisResult(null);

    try {
      const result = await qualityApi.checkWithPrice(file, cropName, region);
      setAnalysisResult(result);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Không thể phân tích ảnh'));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const loadFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    if (selectedImage) {
      URL.revokeObjectURL(selectedImage);
    }
    setSelectedFile(file);
    setSelectedImage(URL.createObjectURL(file));
    setAnalysisResult(null);
    setError(null);
  };

  const handleFileSelect = (event) => {
    loadFile(event.target.files[0]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    loadFile(event.dataTransfer.files[0]);
  };

  const handleReset = () => {
    if (selectedImage) {
      URL.revokeObjectURL(selectedImage);
    }
    setSelectedImage(null);
    setSelectedFile(null);
    setAnalysisResult(null);
    setError(null);
    setIsAnalyzing(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const meta = gradeMeta[analysisResult?.quality_grade] || gradeMeta.grade_1;
  const ResultIcon = meta.icon;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Kiểm Tra Chất Lượng</h1>
        <p className="text-gray-600">
          🍌🍊🥭🍎 Dùng <strong>YOLO11 + EfficientNet</strong> cho quả đã train. Rau củ dùng Gemini Vision.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-6">
              <ImageIcon className="w-6 h-6 text-green-700" />
              <h2 className="text-xl font-bold text-gray-900">Hình Ảnh Đầu Vào</h2>
            </div>

            <div className="grid md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Loại nông sản
                </label>
                <select
                  value={cropName}
                  onChange={(event) => setCropName(event.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <optgroup label="🍌 Quả (YOLO + EfficientNet)">
                    <option value="chuoi">Chuối</option>
                    <option value="xoai">Xoài</option>
                    <option value="tao">Táo</option>
                    <option value="cam">Cam</option>
                  </optgroup>
                  <optgroup label="🥬 Rau củ (Gemini Vision)">
                    <option value="ca chua">Cà chua</option>
                    <option value="dua chuot">Dưa chuột</option>
                    <option value="rau muong">Rau muống</option>
                    <option value="lua">Lúa</option>
                    <option value="ot">Ớt</option>
                    <option value="sau rieng">Sầu riêng</option>
                    <option value="thanh long">Thanh long</option>
                  </optgroup>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Khu vực
                </label>
                <select
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="Ha Noi">Hà Nội</option>
                  <option value="TP.HCM">TP.HCM</option>
                  <option value="Da Nang">Đà Nẵng</option>
                  <option value="Can Tho">Cần Thơ</option>
                </select>
              </div>
            </div>

            {!selectedImage ? (
              <div
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-gray-300 rounded-2xl p-12 text-center hover:border-green-500 hover:bg-green-50 transition cursor-pointer"
              >
                <div className="flex flex-col items-center space-y-4">
                  <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center">
                    <Upload className="w-10 h-10 text-green-700" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">
                      Kéo thả ảnh vào đây
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                      hoặc nhấn để chọn từ thiết bị
                    </p>
                    <div className="flex items-center justify-center space-x-4 text-xs text-gray-500">
                      <span className="flex items-center space-x-1">
                        <FileImage className="w-4 h-4" />
                        <span>PNG</span>
                      </span>
                      <span className="flex items-center space-x-1">
                        <FileImage className="w-4 h-4" />
                        <span>JPG</span>
                      </span>
                    </div>
                  </div>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="relative rounded-2xl overflow-hidden bg-gray-100">
                  <img src={selectedImage} alt="Selected crop" className="w-full h-96 object-cover" />
                  {isAnalyzing && (
                    <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                      <div className="text-center text-white">
                        <div className="w-16 h-16 border-4 border-white border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                        <p className="font-medium">Đang phân tích...</p>
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex space-x-3">
                  <button
                    onClick={handleReset}
                    className="flex-1 px-6 py-3 border-2 border-gray-300 rounded-xl hover:border-red-500 hover:text-red-500 transition font-medium"
                  >
                    Tải Ảnh Khác
                  </button>
                  <button
                    onClick={() => analyzeFile(selectedFile)}
                    disabled={isAnalyzing}
                    className="flex-1 px-6 py-3 bg-green-700 text-white rounded-xl hover:bg-green-800 transition font-medium disabled:bg-gray-300"
                  >
                    {analysisResult ? 'Phân Tích Lại' : 'Phân Tích'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-1 space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-red-700">
              {error}
            </div>
          )}

          {analysisResult ? (
            <div className={`bg-gradient-to-br ${meta.color} rounded-2xl p-6 text-white`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5" />
                  <span className="text-sm font-medium">KẾT QUẢ PHÂN TÍCH</span>
                </div>
                <ResultIcon className="w-6 h-6" />
              </div>

              <div className="mb-3">
                {analysisResult.ai_source === 'yolo_efficientnet' || analysisResult.ai_source === 'efficientnet_fullimage' ? (
                  <span className="inline-flex items-center gap-1 text-xs bg-white/20 rounded-full px-3 py-1 font-medium">
                    🤖 YOLO11 + EfficientNet + HSV
                  </span>
                ) : analysisResult.ai_source === 'gemini_vision' ? (
                  <span className="inline-flex items-center gap-1 text-xs bg-white/20 rounded-full px-3 py-1 font-medium">
                    ✨ Gemini Vision AI
                  </span>
                ) : null}
              </div>

              <div className="mb-6">
                <div className="text-sm opacity-80 mb-2">Phân loại sản phẩm</div>
                <div className="text-4xl font-bold mb-2">{meta.label}</div>
                <div className="text-sm opacity-90">{meta.description}</div>
              </div>

              <div className="space-y-2 mb-6">
                {analysisResult.yolo_confidence > 0 && (
                  <div className="flex items-center justify-between p-2 bg-black/15 rounded-xl text-sm">
                    <span className="opacity-80">YOLO11</span>
                    <span className="font-bold">{(analysisResult.yolo_confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                {analysisResult.efficientnet_confidence > 0 && (
                  <div className="flex items-center justify-between p-2 bg-black/15 rounded-xl text-sm">
                    <span className="opacity-80">EfficientNet</span>
                    <span className="font-bold">{(analysisResult.efficientnet_confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                {analysisResult.hsv_freshness > 0 && (
                  <div className="flex items-center justify-between p-2 bg-black/15 rounded-xl text-sm">
                    <span className="opacity-80">HSV tươi</span>
                    <span className="font-bold">{(analysisResult.hsv_freshness * 100).toFixed(0)}%</span>
                  </div>
                )}
                <div className="flex items-center justify-between p-3 bg-black/15 rounded-xl">
                  <span className="text-sm">Độ tin cậy tổng hợp</span>
                  <span className="font-bold">
                    {((analysisResult.confidence ?? 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              <div className="border-t border-white/25 pt-4">
                <div className="text-sm opacity-80 mb-2">Giá trị ước tính</div>
                <div className="text-3xl font-bold">
                  {analysisResult.suggested_price != null
                    ? analysisResult.suggested_price.toLocaleString()
                    : 'N/A'} VND/kg
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-2xl border-2 border-dashed border-gray-300 p-8 text-center">
              <div className="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
                <Camera className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="font-bold text-gray-900 mb-2">Chờ Phân Tích</h3>
              <p className="text-sm text-gray-600">
                Tải ảnh lên để hệ thống phân tích và hiển thị kết quả.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default QualityCheckPage;
