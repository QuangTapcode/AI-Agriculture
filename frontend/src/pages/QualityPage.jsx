import {
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  Camera,
  CheckCircle2,
  Circle,
  CloudSun,
  Leaf,
  MapPin,
  PackageCheck,
  Sparkles,
  Square,
  Tag,
  TrendingDown,
  Upload,
  Video,
  VideoOff,
  X,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import DataSourceBadge from '../components/DataSourceBadge';
import { getApiErrorMessage } from '../services/api';
import { qualityApi } from '../services/qualityApi';

const REGIONS = ['Hà Nội', 'TP.HCM', 'Đà Nẵng', 'Cần Thơ', 'Hải Phòng', 'Đắk Lắk', 'Tiền Giang'];

const GRADE_COLOR = {
  grade_1: '#22c55e',
  grade_2: '#eab308',
  grade_3: '#f97316',
  damaged: '#ef4444',
};

// Crops supported by YOLO11 + EfficientNet (trained model)
const YOLO_CROPS = [
  { value: 'chuoi',  label: 'Chuối',  emoji: '🍌' },
  { value: 'xoai',   label: 'Xoài',   emoji: '🥭' },
  { value: 'tao',    label: 'Táo',    emoji: '🍎' },
  { value: 'cam',    label: 'Cam',    emoji: '🍊' },
];
// Other crops use Gemini Vision fallback
const GEMINI_CROPS = [
  { value: 'ca chua',    label: 'Cà chua'    },
  { value: 'dua chuot',  label: 'Dưa chuột'  },
  { value: 'sau rieng',  label: 'Sầu riêng'  },
  { value: 'thanh long', label: 'Thanh long'  },
  { value: 'lua',        label: 'Lúa'         },
  { value: '',           label: 'Tự động nhận diện' },
];

const GRADE = {
  grade_1: {
    label: 'Loại 1',
    sub: 'Chất lượng cao',
    badge: 'Xuất khẩu / Siêu thị',
    bg: 'from-emerald-500 to-green-600',
    border: 'border-emerald-200',
    light: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    icon: CheckCircle2,
    dot: 'bg-emerald-500',
    score: (conf) => Math.round(75 + conf * 25),
  },
  grade_2: {
    label: 'Loại 2',
    sub: 'Chất lượng trung bình',
    badge: 'Chợ đầu mối',
    bg: 'from-amber-400 to-yellow-500',
    border: 'border-amber-200',
    light: 'bg-amber-50 text-amber-800 border-amber-200',
    icon: AlertTriangle,
    dot: 'bg-amber-400',
    score: (conf) => Math.round(40 + conf * 30),
  },
  grade_3: {
    label: 'Loại 3',
    sub: 'Chất lượng thấp',
    badge: 'Chế biến / Bán nhanh',
    bg: 'from-red-400 to-rose-600',
    border: 'border-red-200',
    light: 'bg-red-50 text-red-800 border-red-200',
    icon: XCircle,
    dot: 'bg-red-400',
    score: (conf) => Math.round(10 + conf * 28),
  },
};

// ── Score ring ─────────────────────────────────────────────────────────────────
const ScoreRing = ({ score, grade }) => {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = grade === 'grade_1' ? '#10b981' : grade === 'grade_2' ? '#f59e0b' : '#ef4444';
  return (
    <div className="relative flex items-center justify-center w-24 h-24">
      <svg className="absolute inset-0 -rotate-90" width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#e5e7eb" strokeWidth="8" />
        <circle
          cx="48" cy="48" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="text-center z-10">
        <p className="text-2xl font-black text-gray-900 leading-none">{score}</p>
        <p className="text-xs text-gray-400 leading-none mt-0.5">/ 100</p>
      </div>
    </div>
  );
};

// ── Detail row ─────────────────────────────────────────────────────────────────
const Row = ({ icon: Icon, label, children, iconClass = 'text-gray-400' }) => (
  <div className="flex gap-3 py-3 border-b border-gray-50 last:border-0">
    <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${iconClass}`} />
    <div className="flex-1 min-w-0">
      <p className="text-xs font-medium text-gray-400 mb-0.5">{label}</p>
      {children}
    </div>
  </div>
);

// ── Camera Modal (ảnh tĩnh) ────────────────────────────────────────────────────
const CameraModal = ({ onCapture, onClose }) => {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setCameraError] = useState(null);

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then((stream) => {
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => setReady(true);
        }
      })
      .catch(() => setCameraError('Không thể truy cập camera. Vui lòng cho phép quyền camera.'));
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  const capture = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0);
    canvas.toBlob((blob) => {
      const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
      onCapture(file);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    }, 'image/jpeg', 0.92);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Camera className="h-5 w-5 text-emerald-600" />
            <span className="font-bold text-gray-900 text-sm">Chụp ảnh nông sản</span>
          </div>
          <button
            onClick={() => { streamRef.current?.getTracks().forEach((t) => t.stop()); onClose(); }}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="relative bg-black aspect-video flex items-center justify-center">
          {error ? (
            <p className="text-white text-sm px-6 text-center">{error}</p>
          ) : (
            <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
          )}
          {!ready && !error && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60">
              <div className="h-8 w-8 border-2 border-white border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
        <div className="p-4 flex gap-3">
          <button
            onClick={() => { streamRef.current?.getTracks().forEach((t) => t.stop()); onClose(); }}
            className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-semibold text-gray-600 hover:bg-gray-50"
          >Hủy</button>
          <button
            onClick={capture}
            disabled={!ready || !!error}
            className="flex-1 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-200 disabled:text-gray-400 text-white text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
          >
            <Camera className="h-4 w-4" /> Chụp ảnh
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Tracking canvas drawing helpers ───────────────────────────────────────────
const TRACK_COLORS = {
  grade_1: { stroke: '#10b981', fill: 'rgba(16,185,129,0.10)', bg: '#10b981', label: '✓ Chín / Tốt' },
  grade_2: { stroke: '#f59e0b', fill: 'rgba(245,158,11,0.10)',  bg: '#f59e0b', label: '~ Trung bình' },
  grade_3: { stroke: '#ef4444', fill: 'rgba(239,68,68,0.10)',   bg: '#ef4444', label: '✗ Hỏng / Xấu' },
};

// Centered subject box — 68% × 70% of frame, centered
function _subjectBox(w, h) {
  const bw = w * 0.68, bh = h * 0.70;
  return { bx: (w - bw) / 2, by: (h - bh) / 2, bw, bh };
}

function _corners(ctx, x, y, w, h, color, size, lw) {
  ctx.save();
  ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round';
  const s = size;
  ctx.beginPath();
  ctx.moveTo(x, y + s);         ctx.lineTo(x, y);         ctx.lineTo(x + s, y);
  ctx.moveTo(x + w - s, y);     ctx.lineTo(x + w, y);     ctx.lineTo(x + w, y + s);
  ctx.moveTo(x, y + h - s);     ctx.lineTo(x, y + h);     ctx.lineTo(x + s, y + h);
  ctx.moveTo(x + w - s, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - s);
  ctx.stroke();
  ctx.restore();
}

function drawTrackIdle(ctx, w, h) {
  const { bx, by, bw, bh } = _subjectBox(w, h);
  _corners(ctx, bx, by, bw, bh, 'rgba(255,255,255,0.40)', 20, 2.5);
  // Center crosshair
  const cx = bx + bw / 2, cy = by + bh / 2;
  ctx.save();
  ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(cx - 12, cy); ctx.lineTo(cx + 12, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy - 12); ctx.lineTo(cx, cy + 12); ctx.stroke();
  ctx.setLineDash([]);
  ctx.restore();
}

function drawTrackScanning(ctx, w, h) {
  const { bx, by, bw, bh } = _subjectBox(w, h);
  _corners(ctx, bx, by, bw, bh, '#22d3ee', 22, 3.5);
  const progress = (Date.now() % 2200) / 2200;
  const sy = by + progress * bh;
  const grad = ctx.createLinearGradient(0, Math.max(by, sy - 52), 0, sy + 2);
  grad.addColorStop(0, 'rgba(34,211,238,0)');
  grad.addColorStop(1, 'rgba(34,211,238,0.55)');
  ctx.fillStyle = grad;
  ctx.fillRect(bx, Math.max(by, sy - 52), bw, Math.min(52, sy - by + 2));
  ctx.strokeStyle = 'rgba(34,211,238,0.9)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(bx, sy); ctx.lineTo(bx + bw, sy); ctx.stroke();
}

function drawTrackDetected(ctx, w, h, info) {
  const { grade, name, confidence } = info;
  const c = TRACK_COLORS[grade] || TRACK_COLORS.grade_2;
  const { bx, by, bw, bh } = _subjectBox(w, h);
  const pulse = 0.5 + 0.5 * Math.sin(Date.now() / 550);

  ctx.fillStyle = c.fill;
  ctx.fillRect(bx, by, bw, bh);
  ctx.strokeStyle = c.stroke; ctx.lineWidth = 1.5 + pulse * 1.5;
  ctx.strokeRect(bx, by, bw, bh);
  _corners(ctx, bx, by, bw, bh, c.stroke, 24, 4);

  // Label directly above the box top edge
  const crop = name ? name.charAt(0).toUpperCase() + name.slice(1) : 'Nông sản';
  const txt  = `${crop}   ${c.label}   ${(confidence * 100).toFixed(0)}%`;
  ctx.font = 'bold 13px system-ui, -apple-system, sans-serif';
  const lpad = 12, lh = 28;
  const lw2  = ctx.measureText(txt).width + lpad * 2;
  const lx   = bx;
  const ly   = by - lh - 5;

  if (ly >= 2) {
    ctx.fillStyle = c.bg;
    ctx.fillRect(lx, ly, lw2, lh);
    ctx.fillStyle = '#fff';
    ctx.fillText(txt, lx + lpad, ly + 19);
  } else {
    // not enough room above — draw inside top of box with alpha
    ctx.save(); ctx.globalAlpha = 0.88;
    ctx.fillStyle = c.bg; ctx.fillRect(bx, by, lw2, lh);
    ctx.restore();
    ctx.fillStyle = '#fff';
    ctx.fillText(txt, bx + lpad, by + 19);
  }

  // Pulsing dot top-right
  ctx.save();
  ctx.globalAlpha = 0.45 + pulse * 0.55;
  ctx.fillStyle = c.bg;
  ctx.beginPath(); ctx.arc(bx + bw - 14, by + 14, 4 + pulse * 3, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

// ── Video Quality Panel ────────────────────────────────────────────────────────
const VideoQualityPanel = ({ region, onResult, onError, onLoadingChange }) => {
  const videoRef    = useRef(null);
  const captureRef  = useRef(null); // hidden canvas — frame capture
  const overlayRef  = useRef(null); // visible canvas — tracking overlay
  const streamRef   = useRef(null);
  const intervalRef = useRef(null);
  const rafRef      = useRef(null);
  const busyRef     = useRef(false);  // prevents overlapping analyses
  const stoppedRef  = useRef(false);  // true after stopRecording — blocks in-flight results
  const trackRef    = useRef(null);   // trackInfo for rAF (no stale closure)
  const scanningRef = useRef(false);  // scanning state for rAF

  const [cameraReady, setCameraReady]     = useState(false);
  const [cameraError, setCameraError]     = useState(null);
  const [recording,   setRecording]       = useState(false);
  const [liveMode,    setLiveMode]        = useState(true);
  const [capturedFrame, setCapturedFrame] = useState(null); // { url, file, track }
  const [liveAnalyzing, setLiveAnalyzing] = useState(false);
  const [liveCount, setLiveCount]         = useState(0);
  // Lịch sử các lần phân tích trong phiên quay
  const [analyses, setAnalyses]           = useState([]);
  const [selectedId, setSelectedId]       = useState(null); // id của item đang xem chi tiết

  // Camera init
  useEffect(() => {
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1280 } } })
      .then((stream) => {
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => setCameraReady(true);
        }
      })
      .catch(() => setCameraError('Không thể truy cập camera. Vui lòng cho phép quyền camera.'));
    return () => {
      clearInterval(intervalRef.current);
      cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // Tracking animation loop — runs only while recording
  useEffect(() => {
    if (!recording) {
      cancelAnimationFrame(rafRef.current);
      const ov = overlayRef.current;
      if (ov) ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
      return;
    }
    const loop = () => {
      const ov = overlayRef.current;
      if (ov) {
        const cw = ov.clientWidth, ch = ov.clientHeight;
        if (cw > 0 && ch > 0) {
          if (ov.width !== cw) ov.width = cw;
          if (ov.height !== ch) ov.height = ch;
          const ctx = ov.getContext('2d');
          ctx.clearRect(0, 0, cw, ch);
          if (scanningRef.current)   drawTrackScanning(ctx, cw, ch);
          else if (trackRef.current) drawTrackDetected(ctx, cw, ch, trackRef.current);
          else                       drawTrackIdle(ctx, cw, ch);
        }
      }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [recording]);

  const captureFrame = useCallback(() => {
    const v = videoRef.current, c = captureRef.current;
    if (!v || !c || !v.videoWidth) return Promise.resolve(null);
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    return new Promise((res) =>
      c.toBlob(
        (b) => res(b ? new File([b], `frame-${Date.now()}.jpg`, { type: 'image/jpeg' }) : null),
        'image/jpeg', 0.88,
      ),
    );
  }, []);

  const runAnalysis = useCallback(async (file) => {
    if (busyRef.current) return;
    busyRef.current     = true;
    scanningRef.current = true;
    setLiveAnalyzing(true);
    onLoadingChange(true);
    try {
      const result = await qualityApi.checkWithPrice(file, '', region);
      // Nếu đã dừng quay trong lúc API đang chạy → bỏ qua kết quả
      if (stoppedRef.current) return;
      onResult(result, 'video');
      setLiveCount((c) => c + 1);
      if (result.quality_grade) {
        const ti = { grade: result.quality_grade, name: result.detected_crop || '', confidence: result.confidence || 0 };
        trackRef.current = ti;
        const entry = {
          id: Date.now(),
          time: new Date().toLocaleTimeString('vi', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          grade: result.quality_grade,
          name: result.detected_crop || 'Không xác định',
          confidence: result.confidence || 0,
          isProduce: result.is_produce !== false,
          result, // lưu toàn bộ kết quả để xem chi tiết
        };
        setAnalyses((prev) => [entry, ...prev].slice(0, 10));
      }
    } catch (err) {
      if (!stoppedRef.current) onError(getApiErrorMessage(err, 'Lỗi phân tích video'));
    } finally {
      busyRef.current     = false;
      scanningRef.current = false;
      setLiveAnalyzing(false);
      onLoadingChange(false);
    }
  }, [region, onResult, onError, onLoadingChange]);

  const startRecording = () => {
    setCapturedFrame(null);
    trackRef.current    = null;
    scanningRef.current = false;
    stoppedRef.current  = false;
    setRecording(true);
    setLiveCount(0);
    setAnalyses([]);
    setSelectedId(null);
    if (liveMode) {
      captureFrame().then((f) => { if (f) runAnalysis(f); });
      intervalRef.current = setInterval(async () => {
        const f = await captureFrame();
        if (f) runAnalysis(f);
      }, 4000);
    }
  };

  const stopRecording = async () => {
    stoppedRef.current = true;   // block any in-flight API result
    clearInterval(intervalRef.current);
    setRecording(false);
    const f = await captureFrame();
    if (f) setCapturedFrame({ url: URL.createObjectURL(f), file: f, track: trackRef.current });
  };

  const analyzeCapture = async () => {
    if (!capturedFrame) return;
    await runAnalysis(capturedFrame.file);
    // Update track on captured frame after manual analyze
    setCapturedFrame((prev) => prev ? { ...prev, track: trackRef.current } : prev);
  };

  const clearCapture = () => {
    if (capturedFrame?.url) URL.revokeObjectURL(capturedFrame.url);
    setCapturedFrame(null);
    setLiveCount(0);
    trackRef.current = null;
  };

  if (cameraError) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-center px-4">
        <VideoOff className="h-10 w-10 text-gray-300" />
        <p className="text-sm text-gray-500">{cameraError}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <canvas ref={captureRef} className="hidden" />

      {/* ── Live video + tracking overlay ── */}
      <div className="relative bg-black rounded-xl overflow-hidden" style={{ minHeight: '300px' }}>
        <video
          ref={videoRef}
          autoPlay playsInline muted
          className="w-full h-full object-cover"
          style={{ minHeight: '300px' }}
        />
        {/* Tracking overlay canvas */}
        <canvas
          ref={overlayRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />

        {!cameraReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <div className="h-8 w-8 border-2 border-white border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {recording && (
          <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/55 backdrop-blur-sm px-2.5 py-1 rounded-full">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-white text-xs font-semibold">REC</span>
          </div>
        )}
        {recording && liveMode && liveCount > 0 && (
          <div className="absolute top-2 right-2 bg-black/55 backdrop-blur-sm px-2.5 py-0.5 rounded-full text-white text-xs font-bold">
            {liveCount}×
          </div>
        )}
      </div>

      {/* ── Captured frame (large) ── */}
      {capturedFrame && !recording && (
        <div className="relative rounded-xl overflow-hidden border border-gray-200 bg-black">
          <img
            src={capturedFrame.url}
            alt="Frame cuối"
            className="w-full object-contain"
            style={{ maxHeight: '340px' }}
          />
          {/* Quality overlay badge on captured frame */}
          {capturedFrame.track && (() => {
            const tc = TRACK_COLORS[capturedFrame.track.grade] || TRACK_COLORS.grade_2;
            const crop = capturedFrame.track.name
              ? capturedFrame.track.name.charAt(0).toUpperCase() + capturedFrame.track.name.slice(1)
              : 'Nông sản';
            return (
              <div
                className="absolute top-0 left-0 px-3 py-1.5 text-white text-xs font-bold flex items-center gap-2"
                style={{ background: tc.bg }}
              >
                <span>{crop}</span>
                <span className="opacity-80">·</span>
                <span>{tc.label}</span>
                <span className="opacity-80">·</span>
                <span>{(capturedFrame.track.confidence * 100).toFixed(0)}%</span>
              </div>
            );
          })()}
          <div className="absolute bottom-2 left-2 bg-black/55 text-white text-xs px-2 py-0.5 rounded-full font-semibold">
            Frame cuối
          </div>
          <button
            onClick={clearCapture}
            className="absolute bottom-2 right-2 flex items-center gap-1 bg-white/90 hover:bg-red-50 text-gray-500 hover:text-red-600 text-xs px-2.5 py-1 rounded-full border border-gray-200 shadow-sm transition-colors font-medium"
          >
            <X className="h-3 w-3" /> Xóa
          </button>
        </div>
      )}

      {/* Live mode toggle */}
      {!recording && (
        <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
          <div>
            <p className="text-sm font-semibold text-gray-700">Phân tích ngay khi quay</p>
            <p className="text-xs text-gray-400 mt-0.5">AI cập nhật kết quả mỗi 4 giây</p>
          </div>
          <button
            onClick={() => setLiveMode((v) => !v)}
            className={`relative w-11 h-6 rounded-full transition-colors ${liveMode ? 'bg-emerald-500' : 'bg-gray-300'}`}
          >
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${liveMode ? 'translate-x-5' : 'translate-x-0'}`} />
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        {!recording ? (
          <button
            onClick={startRecording}
            disabled={!cameraReady}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-red-500 hover:bg-red-600 disabled:bg-gray-200 disabled:text-gray-400 text-white text-sm font-semibold transition-colors shadow-sm"
          >
            <Circle className="h-4 w-4 fill-white" /> Bắt đầu quay
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-900 text-white text-sm font-semibold transition-colors shadow-sm"
          >
            <Square className="h-4 w-4 fill-white" /> Dừng quay
          </button>
        )}
        {capturedFrame && !recording && !liveMode && (
          <button
            onClick={analyzeCapture}
            disabled={liveAnalyzing}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-200 disabled:text-gray-400 text-white text-sm font-semibold transition-colors shadow-sm"
          >
            {liveAnalyzing ? (
              <><span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Đang phân tích...</>
            ) : (
              <><Sparkles className="h-4 w-4" /> Phân tích frame</>
            )}
          </button>
        )}
      </div>

      {!recording && !capturedFrame && analyses.length === 0 && (
        <p className="text-xs text-gray-400 text-center">
          {liveMode ? 'Nhấn Bắt đầu quay — AI tự phân tích trong lúc bạn quay.' : 'Nhấn Bắt đầu quay → Dừng → Phân tích frame cuối.'}
        </p>
      )}

      {/* ── Lịch sử phân tích ── */}
      {analyses.length > 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Lịch sử phân tích · {analyses.length} lần
            </p>
            <button
              onClick={() => setAnalyses([])}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
            >
              Xóa
            </button>
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-0.5">
            {analyses.map((a, idx) => {
              const c = TRACK_COLORS[a.grade] || TRACK_COLORS.grade_2;
              const cropName = a.name
                ? a.name.charAt(0).toUpperCase() + a.name.slice(1)
                : 'Nông sản';
              const gradeShort = c.label.replace('✓ ', '').replace('~ ', '').replace('✗ ', '');
              const isSelected = selectedId === a.id;
              return (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => {
                    if (isSelected) {
                      setSelectedId(null);
                    } else {
                      setSelectedId(a.id);
                      if (a.result) onResult(a.result, 'video');
                    }
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-left transition-all ${
                    isSelected
                      ? 'border-2 bg-white shadow-sm'
                      : 'border-gray-100 bg-white hover:bg-gray-50 hover:border-gray-200'
                  }`}
                  style={isSelected ? { borderColor: c.bg } : {}}
                >
                  <span className="text-xs text-gray-300 font-mono w-4 shrink-0 text-right">
                    {analyses.length - idx}
                  </span>
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c.bg }} />
                  <span className="text-xs font-semibold text-gray-800 truncate flex-1">{cropName}</span>
                  <span
                    className="text-xs text-white px-1.5 py-0.5 rounded-md font-semibold shrink-0"
                    style={{ background: c.bg }}
                  >
                    {gradeShort}
                  </span>
                  <span className="text-xs text-gray-400 w-8 text-right shrink-0">
                    {(a.confidence * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs text-gray-300 shrink-0 hidden sm:block">{a.time}</span>
                  {isSelected && (
                    <span className="text-xs font-bold shrink-0" style={{ color: c.bg }}>▶</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Main ───────────────────────────────────────────────────────────────────────
const QualityPage = () => {
  const [tab, setTab] = useState('image'); // 'image' | 'video'
  const [resultSource, setResultSource] = useState('image'); // 'image' | 'video'

  // Image tab state
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [imageLoading, setImageLoading] = useState(false);

  // Shared state
  const [region, setRegion] = useState('Đà Nẵng');
  const [cropName, setCropName] = useState('chuoi');
  const [loading, setLoading] = useState(false);
  const [hoveredIdx, setHoveredIdx] = useState(-1);
  const [imgNaturalDims, setImgNaturalDims] = useState({ w: 640, h: 480 });
  const annotationImgRef = useRef(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const applyFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
  };

  const handleFileSelect = (e) => applyFile(e.target.files[0]);
  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    applyFile(e.dataTransfer.files[0]);
  };
  const handleCameraCapture = (file) => { setShowCamera(false); applyFile(file); };
  const clearImage = () => { setPreview(null); setSelectedFile(null); setResult(null); setError(null); };

  const handleImageSubmit = async () => {
    if (!selectedFile) { setError('Vui lòng chọn ảnh'); return; }
    setImageLoading(true);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await qualityApi.checkWithPrice(selectedFile, cropName, region);
      setResult(data);
      setResultSource('image');
      setHoveredIdx(-1);
    } catch (err) {
      setResult(null);
      setError(getApiErrorMessage(err, 'Lỗi khi kiểm tra chất lượng'));
    } finally {
      setImageLoading(false);
      setLoading(false);
    }
  };

  const handleVideoResult = (data, src = 'video') => {
    setResult(data);
    setResultSource(src);
    setError(null);
  };
  const handleVideoError = (msg) => setError(msg);
  const handleVideoLoadingChange = (v) => setLoading(v);

  const g = result ? (GRADE[result.quality_grade] ?? GRADE.grade_2) : null;
  const score = g ? g.score(result.confidence) : 0;
  const GradeIcon = g?.icon;
  const discountPct = result?.quality_multiplier != null && result.quality_multiplier < 1
    ? Math.round((1 - result.quality_multiplier) * 100) : 0;
  const isProduce = result?.is_produce !== false;

  return (
    <div className="min-h-screen bg-gray-50">
      {showCamera && (
        <CameraModal onCapture={handleCameraCapture} onClose={() => setShowCamera(false)} />
      )}

      {/* ── Page header ── */}
      <div className="bg-white border-b border-gray-100 px-6 py-5">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <div className="p-2 rounded-xl bg-emerald-50">
            <Sparkles className="h-5 w-5 text-emerald-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Kiểm định chất lượng nông sản</h1>
            <p className="text-sm text-gray-500">
              {YOLO_CROPS.some((c) => c.value === cropName)
                ? '🤖 YOLO11 + EfficientNet — AI local, nhanh, không cần internet'
                : '✨ Gemini Vision — AI cloud, nhận diện đa dạng nông sản'}
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* ── LEFT: Input panel ────────────────────────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Crop + Region selectors */}
          <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm space-y-3">
            {/* Crop selector */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                <Leaf className="h-4 w-4 text-emerald-500" /> Loại nông sản
              </label>
              <select
                value={cropName}
                onChange={(e) => setCropName(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-gray-50"
              >
                <optgroup label="🤖 YOLO11 + EfficientNet (AI local)">
                  {YOLO_CROPS.map((c) => (
                    <option key={c.value} value={c.value}>{c.emoji} {c.label}</option>
                  ))}
                </optgroup>
                <optgroup label="✨ Gemini Vision (AI cloud)">
                  {GEMINI_CROPS.map((c) => (
                    <option key={c.value || '_auto'} value={c.value}>{c.label}</option>
                  ))}
                </optgroup>
              </select>
              {YOLO_CROPS.some((c) => c.value === cropName) && (
                <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                  Dùng YOLO11 + EfficientNet — nhanh, không cần internet
                </p>
              )}
            </div>

            {/* Region selector */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                <MapPin className="h-4 w-4 text-emerald-500" /> Khu vực thị trường
              </label>
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-gray-50"
              >
                {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>

          {/* Tab selector */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex border-b border-gray-100">
              <button
                onClick={() => setTab('image')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-colors ${tab === 'image' ? 'bg-emerald-50 text-emerald-700 border-b-2 border-emerald-500' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                <Camera className="h-4 w-4" /> Ảnh
              </button>
              <button
                onClick={() => setTab('video')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-colors ${tab === 'video' ? 'bg-rose-50 text-rose-700 border-b-2 border-rose-500' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}
              >
                <Video className="h-4 w-4" /> Video
              </button>
            </div>

            {/* ── Image tab ── */}
            {tab === 'image' && (
              <div>
                <div
                  className={`relative min-h-[220px] flex items-center justify-center transition-colors ${dragOver ? 'bg-emerald-50' : 'bg-gray-50'}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                >
                  {preview ? (
                    <img src={preview} alt="Preview" className="w-full max-h-64 object-contain" />
                  ) : (
                    <div className="flex flex-col items-center gap-3 p-6 w-full">
                      <button
                        type="button"
                        onClick={() => setShowCamera(true)}
                        className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-sm font-semibold shadow-sm transition-colors"
                      >
                        <Camera className="h-4 w-4" /> Chụp ảnh bằng camera
                      </button>
                      <div className="flex items-center gap-3 w-full max-w-xs">
                        <div className="flex-1 h-px bg-gray-200" />
                        <span className="text-xs text-gray-400">hoặc</span>
                        <div className="flex-1 h-px bg-gray-200" />
                      </div>
                      <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-2 w-full">
                        <div className={`p-4 rounded-2xl border-2 border-dashed transition-colors ${dragOver ? 'border-emerald-400 bg-emerald-100' : 'border-gray-300 bg-white'}`}>
                          <Upload className={`h-8 w-8 ${dragOver ? 'text-emerald-500' : 'text-gray-300'}`} />
                        </div>
                        <div className="text-center">
                          <p className="text-sm font-semibold text-emerald-600">Kéo thả hoặc chọn ảnh</p>
                          <p className="text-xs text-gray-400 mt-1">PNG, JPG, WEBP — tối đa 10MB</p>
                        </div>
                        <input id="file-upload" type="file" className="sr-only" accept="image/*" onChange={handleFileSelect} />
                      </label>
                    </div>
                  )}
                  {preview && (
                    <button
                      onClick={clearImage}
                      className="absolute top-2 right-2 bg-white/90 hover:bg-white text-gray-500 hover:text-red-500 text-xs px-2.5 py-1 rounded-full border border-gray-200 shadow-sm transition-colors"
                    >
                      Xóa ảnh
                    </button>
                  )}
                </div>
                <div className="p-4 border-t border-gray-100">
                  {error && tab === 'image' && (
                    <div className="mb-3 p-3 bg-red-50 rounded-xl border border-red-200 text-sm text-red-600">{error}</div>
                  )}
                  <button
                    onClick={handleImageSubmit}
                    disabled={!selectedFile || imageLoading}
                    className="w-full bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-700 hover:to-green-700 text-white py-3 px-4 rounded-xl text-sm font-semibold disabled:from-gray-200 disabled:to-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-all shadow-sm"
                  >
                    {imageLoading ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        AI đang phân tích...
                      </span>
                    ) : (
                      <span className="flex items-center justify-center gap-2">
                        <Sparkles className="h-4 w-4" /> Phân tích chất lượng
                      </span>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* ── Video tab ── */}
            {tab === 'video' && (
              <div className="p-4">
                {error && tab === 'video' && (
                  <div className="mb-3 p-3 bg-red-50 rounded-xl border border-red-200 text-sm text-red-600">{error}</div>
                )}
                <VideoQualityPanel
                  region={region}
                  onResult={handleVideoResult}
                  onError={handleVideoError}
                  onLoadingChange={handleVideoLoadingChange}
                />
              </div>
            )}
          </div>

          {/* Tips — chỉ hiện khi chưa có kết quả */}
          {!result && (
            <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm space-y-2">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {tab === 'video' ? 'Mẹo quay video' : 'Để kết quả chính xác'}
              </p>
              {(tab === 'video'
                ? ['Giữ camera ổn định, đủ ánh sáng', 'Đưa nông sản vào giữa khung hình', 'Quay chậm để AI nhận diện rõ hơn', 'Bật "Phân tích ngay khi quay" để xem kết quả liên tục']
                : ['Chụp rõ mặt quả, đủ ánh sáng', 'Đặt quả trên nền đơn giản', 'Ảnh ≥ 500×500 px, không mờ', 'Có thể chụp cả quả hoặc mặt cắt']
              ).map((t) => (
                <div key={t} className="flex items-center gap-2 text-xs text-gray-600">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${tab === 'video' ? 'bg-rose-400' : 'bg-emerald-400'}`} />
                  {t}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── RIGHT: Results ───────────────────────────────────────────────── */}
        <div className="lg:col-span-3">
          {!result && !loading && (
            <div className="h-full min-h-[400px] bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col items-center justify-center gap-4 text-gray-300">
              {tab === 'video' ? <Video className="h-16 w-16" /> : <Camera className="h-16 w-16" />}
              <div className="text-center">
                <p className="text-base font-semibold text-gray-400">Chưa có kết quả phân tích</p>
                <p className="text-sm mt-1">
                  {tab === 'video'
                    ? 'Quay video nông sản — AI sẽ định giá ngay khi quay hoặc khi bạn dừng lại'
                    : 'Chụp ảnh hoặc tải ảnh nông sản để AI đánh giá chất lượng và định giá'}
                </p>
              </div>
            </div>
          )}

          {loading && (
            <div className="min-h-[400px] bg-white rounded-2xl border border-gray-200 shadow-sm flex flex-col items-center justify-center gap-4">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-4 border-emerald-100 border-t-emerald-500 animate-spin" />
                <Sparkles className="absolute inset-0 m-auto h-6 w-6 text-emerald-500" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-700">AI đang phân tích {resultSource === 'video' ? 'video' : 'hình ảnh'}</p>
                <p className="text-xs text-gray-400 mt-1">Nhận diện loại quả · Đánh giá màu sắc · Phát hiện khuyết tật</p>
              </div>
            </div>
          )}

          {result && g && (
            <div className="space-y-4">

              {/* Source badge video */}
              {resultSource === 'video' && (
                <div className="flex items-center gap-2 px-3 py-2 bg-rose-50 border border-rose-200 rounded-xl">
                  <Video className="h-4 w-4 text-rose-500 shrink-0" />
                  <p className="text-xs font-medium text-rose-700">Kết quả từ phân tích video — AI cập nhật liên tục khi quay</p>
                </div>
              )}

              {/* Non-produce warning */}
              {!isProduce && (
                <div className="flex items-start gap-3 p-4 bg-orange-50 border border-orange-200 rounded-2xl">
                  <AlertTriangle className="h-5 w-5 text-orange-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-orange-800">Không phải nông sản</p>
                    <p className="text-sm text-orange-700 mt-0.5">
                      AI không nhận diện được nông sản — không thể định giá thị trường. Vui lòng hướng camera vào rau, củ, quả.
                    </p>
                  </div>
                </div>
              )}

              {/* Hero card */}
              {isProduce && (
                <div className={`rounded-2xl bg-gradient-to-br ${g.bg} p-5 text-white shadow-md`}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="mb-3 flex flex-wrap items-center gap-2">
                        {result.ai_source === 'yolo_efficientnet' || result.ai_source === 'efficientnet_fullimage' ? (
                          <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-semibold flex items-center gap-1">
                            🤖 YOLO11 + EfficientNet + HSV
                          </span>
                        ) : result.ai_source === 'gemini_vision' ? (
                          <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-semibold">
                            ✨ Gemini Vision
                          </span>
                        ) : (
                          <DataSourceBadge data={result} className="bg-white/90" />
                        )}
                        {Number.isFinite(result.confidence) && (
                          <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-semibold">
                            Độ tin cậy {(result.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      {result.detected_crop && (
                        <div className="inline-flex items-center gap-1.5 bg-white/20 backdrop-blur-sm px-3 py-1 rounded-full text-xs font-semibold mb-3">
                          <BadgeCheck className="h-3.5 w-3.5" />
                          AI nhận diện: <span className="capitalize ml-0.5">{result.detected_crop}</span>
                        </div>
                      )}
                      <p className="text-white/80 text-sm font-medium">Phân loại chất lượng</p>
                      <p className="text-3xl font-black mt-0.5">{g.label}</p>
                      <p className="text-white/80 text-sm mt-0.5">{g.sub}</p>
                      <div className="mt-3 inline-flex items-center gap-1.5 bg-white/20 px-3 py-1 rounded-full text-xs font-medium">
                        <PackageCheck className="h-3.5 w-3.5" /> {g.badge}
                      </div>
                    </div>
                    <div className="shrink-0 bg-white/15 rounded-2xl p-3">
                      <ScoreRing score={score} grade={result.quality_grade} />
                      <p className="text-center text-xs text-white/70 mt-1">Điểm chất lượng</p>
                    </div>
                  </div>
                  <div className="mt-4 bg-white/15 rounded-xl p-3">
                    <div className="flex justify-between text-xs text-white/80 mb-1.5">
                      <span>Độ tin cậy AI</span>
                      <span className="font-bold">{(result.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2 bg-white/20 rounded-full overflow-hidden">
                      <div className="h-full bg-white rounded-full transition-all duration-700" style={{ width: `${(result.confidence * 100).toFixed(0)}%` }} />
                    </div>
                  </div>
                </div>
              )}

              {/* Interactive fruit detection panel */}
              {(result.all_detections || []).length > 0 && preview && (
                <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                    <span className="text-sm font-bold text-gray-800 flex items-center gap-2">
                      🔍 Phát hiện {(result.all_detections || []).length} quả
                    </span>
                    <span className="text-xs text-gray-400">
                      {hoveredIdx >= 0 ? `Đang xem quả #${hoveredIdx + 1}` : 'Hover để xem từng quả'}
                    </span>
                  </div>

                  {/* Image + SVG box overlay */}
                  <div className="relative select-none">
                    <img
                      ref={annotationImgRef}
                      src={preview}
                      alt="Fruit detection"
                      className="w-full object-contain max-h-72 block"
                      onLoad={() => {
                        if (annotationImgRef.current) {
                          setImgNaturalDims({
                            w: annotationImgRef.current.naturalWidth,
                            h: annotationImgRef.current.naturalHeight,
                          });
                        }
                      }}
                    />
                    {/* SVG overlay — viewBox = original image dims, auto-scales */}
                    <svg
                      className="absolute inset-0 w-full h-full pointer-events-none"
                      viewBox={`0 0 ${imgNaturalDims.w} ${imgNaturalDims.h}`}
                      preserveAspectRatio="xMidYMid meet"
                    >
                      <defs>
                        <filter id="glow">
                          <feGaussianBlur stdDeviation="3" result="blur" />
                          <feComposite in="SourceGraphic" in2="blur" operator="over" />
                        </filter>
                      </defs>
                      {(result.all_detections || []).map((det, i) => {
                        const bbox = det.bbox || [];
                        if (bbox.length < 4) return null;
                        const [x1, y1, x2, y2] = bbox;
                        const w = x2 - x1, h = y2 - y1;
                        const color = GRADE_COLOR[det.grade] ?? '#94a3b8';
                        const isHovered = hoveredIdx === i;
                        const isOther = hoveredIdx >= 0 && !isHovered;
                        return (
                          <g key={i}>
                            {/* Box */}
                            <rect
                              x={x1} y={y1} width={w} height={h}
                              rx={8} ry={8}
                              fill={isHovered ? `${color}30` : isOther ? 'transparent' : `${color}18`}
                              stroke={color}
                              strokeWidth={isHovered ? 3 : isOther ? 1 : 2}
                              opacity={isOther ? 0.35 : 1}
                              filter={isHovered ? 'url(#glow)' : 'none'}
                              strokeDasharray={isHovered ? 'none' : 'none'}
                            />
                            {/* Number badge */}
                            <circle
                              cx={x1 + 14} cy={y1 + 14} r={13}
                              fill={isOther ? '#94a3b8' : color}
                              opacity={isOther ? 0.35 : 1}
                            />
                            <text
                              x={x1 + 14} y={y1 + 19}
                              textAnchor="middle"
                              fill="white"
                              fontSize={imgNaturalDims.w > 800 ? 14 : 12}
                              fontWeight="bold"
                              opacity={isOther ? 0.5 : 1}
                            >
                              {i + 1}
                            </text>
                            {/* Label on hover */}
                            {isHovered && (
                              <g>
                                <rect
                                  x={x1} y={y1 - 30} width={Math.min(w, 160)} height={26}
                                  rx={6} fill={color}
                                />
                                <text
                                  x={x1 + 8} y={y1 - 12}
                                  fill="white"
                                  fontSize={imgNaturalDims.w > 800 ? 13 : 11}
                                  fontWeight="600"
                                >
                                  {det.fruit_type_vi} · {det.grade_label_vi} {(det.confidence * 100).toFixed(0)}%
                                </text>
                              </g>
                            )}
                          </g>
                        );
                      })}
                    </svg>
                  </div>

                  {/* Per-fruit interactive list */}
                  <div className="p-3 space-y-1.5 max-h-52 overflow-y-auto">
                    {(result.all_detections || []).map((det, i) => {
                      const g2 = GRADE[det.grade] ?? GRADE.grade_2;
                      const color = GRADE_COLOR[det.grade] ?? '#94a3b8';
                      const isHovered = hoveredIdx === i;
                      return (
                        <div
                          key={i}
                          onMouseEnter={() => setHoveredIdx(i)}
                          onMouseLeave={() => setHoveredIdx(-1)}
                          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border cursor-pointer transition-all duration-150
                            ${isHovered
                              ? 'shadow-md scale-[1.01]'
                              : 'hover:shadow-sm hover:scale-[1.005]'}
                            ${g2.border} ${isHovered ? g2.light : 'bg-white'}`}
                          style={{ borderLeftWidth: 3, borderLeftColor: isHovered ? color : 'transparent' }}
                        >
                          {/* Colored number */}
                          <span
                            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 transition-transform"
                            style={{ background: color, transform: isHovered ? 'scale(1.15)' : 'scale(1)' }}
                          >
                            {i + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-gray-900 truncate">
                              {det.fruit_type_vi} — {det.grade_label_vi}
                            </p>
                            <p className="text-xs text-gray-400">
                              YOLO {(det.yolo_confidence * 100).toFixed(0)}%
                              {det.efficientnet_confidence > 0 && ` · CNN ${(det.efficientnet_confidence * 100).toFixed(0)}%`}
                            </p>
                          </div>
                          <div className="text-right shrink-0">
                            <span className="text-sm font-bold" style={{ color }}>
                              {(det.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Analysis cards grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

                {/* Visual analysis */}
                <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 rounded-lg bg-purple-50">
                      {resultSource === 'video' ? <Video className="h-4 w-4 text-purple-500" /> : <Camera className="h-4 w-4 text-purple-500" />}
                    </div>
                    <span className="text-sm font-bold text-gray-800">Phân tích {resultSource === 'video' ? 'video' : 'hình ảnh'}</span>
                  </div>
                  {/* AI confidence breakdown for YOLO */}
                  {(result.yolo_confidence > 0 || result.efficientnet_confidence > 0) && (
                    <div className="mb-3 space-y-1.5">
                      {result.yolo_confidence > 0 && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">YOLO11</span>
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-emerald-500 rounded-full" style={{width:`${(result.yolo_confidence*100).toFixed(0)}%`}}/>
                            </div>
                            <span className="font-semibold text-gray-700 w-8 text-right">{(result.yolo_confidence*100).toFixed(0)}%</span>
                          </div>
                        </div>
                      )}
                      {result.efficientnet_confidence > 0 && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">EfficientNet</span>
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-500 rounded-full" style={{width:`${(result.efficientnet_confidence*100).toFixed(0)}%`}}/>
                            </div>
                            <span className="font-semibold text-gray-700 w-8 text-right">{(result.efficientnet_confidence*100).toFixed(0)}%</span>
                          </div>
                        </div>
                      )}
                      {result.hsv_freshness > 0 && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">HSV tươi</span>
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-yellow-400 rounded-full" style={{width:`${(result.hsv_freshness*100).toFixed(0)}%`}}/>
                            </div>
                            <span className="font-semibold text-gray-700 w-8 text-right">{(result.hsv_freshness*100).toFixed(0)}%</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {result.color_assessment && (
                    <Row icon={Leaf} label="Màu sắc & tình trạng" iconClass="text-green-500">
                      <p className="text-sm text-gray-700">{result.color_assessment}</p>
                    </Row>
                  )}
                  {result.defects?.length > 0 ? (
                    <Row icon={AlertTriangle} label="Khuyết tật phát hiện" iconClass="text-red-400">
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {result.defects.map((d) => (
                          <span key={d} className="px-2.5 py-1 bg-red-50 text-red-600 text-xs rounded-full border border-red-100 font-medium">{d}</span>
                        ))}
                      </div>
                    </Row>
                  ) : (
                    <Row icon={CheckCircle2} label="Khuyết tật" iconClass="text-emerald-500">
                      <p className="text-sm text-emerald-600 font-medium">Không phát hiện khuyết tật</p>
                    </Row>
                  )}
                </div>

                {/* Reasoning (YOLO/EfficientNet) */}
                {result.reasoning && (
                  <div className="sm:col-span-2 bg-white rounded-2xl border border-gray-200 p-4 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="p-1.5 rounded-lg bg-violet-50">
                        <Sparkles className="h-4 w-4 text-violet-500" />
                      </div>
                      <span className="text-sm font-bold text-gray-800">Lý do phân loại</span>
                    </div>
                    <p className="text-sm text-gray-600 leading-relaxed">{result.reasoning}</p>
                  </div>
                )}

                {/* Price */}
                {isProduce && (
                  <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="p-1.5 rounded-lg bg-blue-50">
                        <BarChart3 className="h-4 w-4 text-blue-500" />
                      </div>
                      <span className="text-sm font-bold text-gray-800">Định giá thị trường</span>
                    </div>
                    {result.price_unavailable ? (
                      <div className="flex items-center gap-2 py-2 text-sm text-amber-700 bg-amber-50 rounded-xl px-3 border border-amber-200">
                        <AlertTriangle className="h-4 w-4 shrink-0" />
                        Chưa có dữ liệu giá cho nông sản này tại khu vực đã chọn.
                      </div>
                    ) : (
                      <>
                        <Row icon={MapPin} label={`Khu vực ${result.region}`} iconClass="text-blue-400">
                          <p className="text-xl font-black text-gray-900">
                            {result.suggested_price_range.min.toLocaleString('vi-VN')}
                            <span className="text-base font-medium text-gray-400 mx-1">–</span>
                            {result.suggested_price_range.max.toLocaleString('vi-VN')}
                            <span className="text-sm font-medium text-gray-500 ml-1">đ/kg</span>
                          </p>
                        </Row>
                        {discountPct > 0 && (
                          <Row icon={TrendingDown} label="Hệ số chất lượng" iconClass="text-orange-400">
                            <span className="px-2.5 py-1 bg-orange-50 text-orange-700 border border-orange-200 text-xs rounded-full font-semibold">
                              Giảm {discountPct}% do chất lượng
                            </span>
                          </Row>
                        )}
                        <Row icon={Tag} label="Nguồn giá" iconClass="text-gray-300">
                          <p className="text-xs text-gray-500">
                            {result.price_source === 'market_db' ? '✓ Giá thị trường thực tế' : '~ Ước tính'}
                            {result.weather_summary ? ` · ${result.weather_summary}` : ''}
                          </p>
                        </Row>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Reasoning */}
              {result.reasoning && (
                <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 rounded-lg bg-indigo-50">
                      <Sparkles className="h-4 w-4 text-indigo-500" />
                    </div>
                    <span className="text-sm font-bold text-gray-800">Lý do phân loại</span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed">{result.reasoning}</p>
                </div>
              )}

              {/* Recommendations */}
              {result.recommendations?.length > 0 && isProduce && (
                <div className={`rounded-2xl border p-4 shadow-sm ${g.light}`}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="p-1.5 rounded-lg bg-white/60">
                      <CloudSun className="h-4 w-4" />
                    </div>
                    <span className="text-sm font-bold">Khuyến nghị xử lý & bán hàng</span>
                  </div>
                  <div className="space-y-2">
                    {result.recommendations.map((r, i) => (
                      <div key={r} className="flex items-start gap-2.5">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/70 text-xs font-bold">{i + 1}</span>
                        <p className="text-sm leading-relaxed">{r}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Weather impact */}
              {result.weather_explanation && isProduce && (
                <div className="bg-white rounded-2xl border border-gray-200 p-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 rounded-lg bg-sky-50">
                      <CloudSun className="h-4 w-4 text-sky-500" />
                    </div>
                    <span className="text-sm font-bold text-gray-800">Ảnh hưởng thời tiết đến giá</span>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">{result.weather_explanation}</p>
                  {result.price_change_pct != null && result.price_change_pct !== 0 && (
                    <div className={`mt-2 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full ${result.price_change_pct > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                      {result.price_change_pct > 0 ? '+' : ''}{result.price_change_pct.toFixed(1)}% so với giá cơ sở
                    </div>
                  )}
                </div>
              )}

            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default QualityPage;
