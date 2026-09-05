import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AgriNavbar from "../components/AgriNavbar";
import logo from "../assets/agri-ai-logo.png";
import { useAuth } from "../contexts/AuthContext";

const featureBullets = [
  "Theo dõi thời tiết, giá nông sản và cảnh báo quan trọng",
  "Lưu lịch sử mùa vụ, dự báo thu hoạch và khuyến nghị AI",
  "Truy cập bảng điều khiển quản lý dữ liệu nông nghiệp tập trung",
];

const pickFunction = (moduleObject, names) => {
  for (const name of names) {
    if (typeof moduleObject?.[name] === "function") return moduleObject[name];
    if (typeof moduleObject?.default?.[name] === "function") return moduleObject.default[name];
  }
  if (typeof moduleObject?.default === "function") return moduleObject.default;
  return null;
};

const callAuthFunction = async (fn, payload) => {
  try {
    return await fn(payload);
  } catch (firstError) {
    try {
      return await fn(payload.email, payload.password, payload.name || payload.fullName || payload.phone);
    } catch {
      throw firstError;
    }
  }
};

const normalizeResponse = (response) => response?.data ?? response ?? {};

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    password: "",
  });

  const isRegister = mode === "register";

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!form.email || !form.password) {
      setError("Vui lòng nhập email và mật khẩu.");
      return;
    }

    if (isRegister && !form.name) {
      setError("Vui lòng nhập họ tên để tạo tài khoản.");
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register({
          fullName: form.name,
          email: form.email,
          password: form.password,
          phoneNumber: form.phone || null,
          zaloId: null,
          region: null,
        });
        setSuccess("Tạo tài khoản thành công. Đang chuyển vào hệ thống...");
      } else {
        await login({
          email: form.email,
          password: form.password,
        });
        setSuccess("Đăng nhập thành công. Đang chuyển vào hệ thống...");
      }

      const returnUrl = sessionStorage.getItem('returnUrl');
      sessionStorage.removeItem('returnUrl');
      setTimeout(() => navigate(returnUrl || '/dashboard'), 450);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || err?.response?.data?.message;
      if (status === 503) {
        setError("Hệ thống đang bảo trì hoặc máy chủ cơ sở dữ liệu chưa khởi động. Vui lòng thử lại sau.");
      } else if (status === 401) {
        setError("Email hoặc mật khẩu không đúng. Vui lòng kiểm tra lại.");
      } else if (status === 409) {
        setError("Email này đã được đăng ký. Vui lòng đăng nhập hoặc dùng email khác.");
      } else if (status === 422) {
        const validationErrors = err?.response?.data?.detail;
        if (Array.isArray(validationErrors)) {
          setError(validationErrors.map((e) => e.msg).join(", "));
        } else {
          setError(detail || "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại.");
        }
      } else if (!err?.response) {
        setError("Không thể kết nối máy chủ. Vui lòng kiểm tra backend đang chạy trên cổng 8000.");
      } else {
        setError(detail || err?.message || "Đã xảy ra lỗi. Vui lòng thử lại.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <AgriNavbar />

      <section className="relative overflow-hidden bg-gradient-to-br from-slate-950 via-emerald-950 to-green-800">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.18),transparent_30%),radial-gradient(circle_at_bottom_left,rgba(132,204,22,0.22),transparent_34%)]" />
        <div className="relative mx-auto grid min-h-[calc(100vh-80px)] max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:px-8 lg:py-16">
          <div className="text-white">
            <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm font-bold text-emerald-50 backdrop-blur">
              🔐 Cổng đăng nhập AgriAI
            </span>
            <h1 className="mt-6 max-w-3xl text-4xl font-black tracking-tight sm:text-5xl lg:text-6xl">
              Truy cập hệ thống AI hỗ trợ nông nghiệp thông minh
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-emerald-50 sm:text-lg">
              Giao diện đăng nhập được đồng bộ với trang giới thiệu, tính năng, bài viết, gói dịch vụ và liên hệ: có logo, thanh điều hướng mới, nút hành động rõ ràng và bố cục hiện đại hơn.
            </p>

            <div className="mt-8 grid gap-3 sm:max-w-xl">
              {featureBullets.map((item) => (
                <div key={item} className="flex items-start gap-3 rounded-3xl border border-white/15 bg-white/10 p-4 backdrop-blur">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-300 text-sm font-black text-emerald-950">✓</span>
                  <p className="font-semibold text-emerald-50">{item}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/features" className="rounded-2xl bg-white px-5 py-3 font-black text-emerald-800 shadow-lg shadow-black/10 transition hover:-translate-y-0.5 hover:bg-emerald-50">
                Xem tính năng
              </Link>
              <Link to="/ai-chat" className="rounded-2xl border border-white/30 px-5 py-3 font-black text-white transition hover:-translate-y-0.5 hover:bg-white/10">
                Hỏi AI trước
              </Link>
            </div>
          </div>

          <div className="mx-auto w-full max-w-md">
            <div className="rounded-[2rem] border border-white/20 bg-white p-6 shadow-2xl shadow-slate-950/20 sm:p-8">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-3xl border border-emerald-100 bg-white shadow-sm">
                  <img src={logo} alt="AgriAI logo" className="h-full w-full object-cover object-center" />
                </div>
                <div>
                  <p className="text-sm font-black uppercase tracking-wide text-emerald-600">AgriAI Account</p>
                  <h2 className="text-2xl font-black text-slate-950">{isRegister ? "Tạo tài khoản" : "Đăng nhập"}</h2>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 rounded-2xl bg-slate-100 p-1">
                <button
                  type="button"
                  onClick={() => setMode("login")}
                  className={`rounded-xl px-4 py-3 text-sm font-black transition ${!isRegister ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500 hover:text-emerald-700"}`}
                >
                  Đăng nhập
                </button>
                <button
                  type="button"
                  onClick={() => setMode("register")}
                  className={`rounded-xl px-4 py-3 text-sm font-black transition ${isRegister ? "bg-white text-emerald-700 shadow-sm" : "text-slate-500 hover:text-emerald-700"}`}
                >
                  Đăng ký
                </button>
              </div>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                {isRegister && (
                  <div>
                    <label className="mb-2 block text-sm font-black text-slate-700">Họ tên</label>
                    <input
                      value={form.name}
                      onChange={(event) => updateField("name", event.target.value)}
                      placeholder="Nguyễn Văn A"
                      className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-semibold outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                    />
                  </div>
                )}

                {isRegister && (
                  <div>
                    <label className="mb-2 block text-sm font-black text-slate-700">Số điện thoại</label>
                    <input
                      value={form.phone}
                      onChange={(event) => updateField("phone", event.target.value)}
                      placeholder="0901 234 567"
                      className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-semibold outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                    />
                  </div>
                )}

                <div>
                  <label className="mb-2 block text-sm font-black text-slate-700">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(event) => updateField("email", event.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-semibold outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                  />
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <label className="block text-sm font-black text-slate-700">Mật khẩu</label>
                    {!isRegister && (
                      <button type="button" className="text-xs font-black text-emerald-700 hover:text-emerald-800">
                        Quên mật khẩu?
                      </button>
                    )}
                  </div>
                  <input
                    type="password"
                    value={form.password}
                    onChange={(event) => updateField("password", event.target.value)}
                    placeholder="Nhập mật khẩu"
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 font-semibold outline-none transition focus:border-emerald-400 focus:bg-white focus:ring-4 focus:ring-emerald-100"
                  />
                </div>

                {error && <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</div>}
                {success && <div className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-700">{success}</div>}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full rounded-2xl bg-emerald-600 px-5 py-4 font-black text-white shadow-lg shadow-emerald-600/20 transition hover:-translate-y-0.5 hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {loading ? "Đang xử lý..." : isRegister ? "Tạo tài khoản AgriAI" : "Đăng nhập vào hệ thống"}
                </button>
              </form>

              <p className="mt-5 text-center text-sm font-semibold text-slate-500">
                {isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"}{" "}
                <button
                  type="button"
                  onClick={() => setMode(isRegister ? "login" : "register")}
                  className="font-black text-emerald-700 hover:text-emerald-800"
                >
                  {isRegister ? "Đăng nhập ngay" : "Đăng ký miễn phí"}
                </button>
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
