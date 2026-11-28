import React, { useState } from 'react';
import { ShieldCheck, Lock, Mail, LogIn, AlertCircle, Store, User, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import { Button } from './ui';

export default function LoginView({ onLoginSuccess }) {
  const [mode, setMode] = useState('login'); // 'login' | 'trial'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [shopName, setShopName] = useState('');
  const [industry, setIndustry] = useState('raincoat');
  const [seedSampleData, setSeedSampleData] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password) return;
    try {
      setSubmitting(true);
      setError('');
      if (mode === 'trial') {
        const res = await api.registerTrial({
          email: email.trim(),
          password,
          full_name: fullName.trim() || email.trim(),
          shop_name: shopName.trim(),
          industry,
          seed_sample_data: seedSampleData,
        });
        onLoginSuccess?.(res.user);
      } else {
        const res = await api.login(email.trim(), password);
        onLoginSuccess?.(res.user);
      }
    } catch (err) {
      setError(err.message || 'Xác thực thất bại. Vui lòng kiểm tra thông tin.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4 py-10">
      <div className="w-full max-w-md rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-7 space-y-5">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-indigo-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            EcomReview AI — Cổng Vận Hành
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {mode === 'trial'
              ? 'Khởi tạo Workspace dùng thử miễn phí 14 ngày trong 1 phút'
              : 'Đăng nhập bằng tài khoản gian hàng được cấp để truy cập dữ liệu và kế hoạch hành động'}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-semibold">
          <button
            type="button"
            onClick={() => {
              setMode('login');
              setError('');
            }}
            className={`py-2 rounded-lg transition ${
              mode === 'login'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('trial');
              setError('');
            }}
            className={`py-2 rounded-lg transition ${
              mode === 'trial'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Dùng thử 14 ngày
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-start gap-2 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === 'trial' && (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Tên gian hàng đầu tiên
                </label>
                <div className="relative">
                  <Store className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    value={shopName}
                    onChange={(e) => setShopName(e.target.value)}
                    placeholder="VD: Lumina Beauty Shop"
                    className="w-full h-10 pl-9 pr-3 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Ngành hàng
                  </label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full h-10 px-2.5 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  >
                    <option value="raincoat">Áo mưa & Đồ đi mưa</option>
                    <option value="fashion">Thời trang & May mặc</option>
                    <option value="cosmetics">Mỹ phẩm & Chăm sóc da</option>
                    <option value="home_living">Gia dụng & Đời sống</option>
                    <option value="electronics">Phụ kiện & Điện tử</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Họ tên chủ shop
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Nguyễn Văn A"
                      className="w-full h-10 pl-9 pr-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                    />
                  </div>
                </div>
              </div>
            </>
          )}

          <div>
            <label
              htmlFor="login-email"
              className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1"
            >
              Email đăng nhập
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="login-email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@shop.vn"
                className="w-full h-10 pl-9 pr-3 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="login-password"
              className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1"
            >
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="login-password"
                type="password"
                required
                minLength={mode === 'trial' ? 6 : 1}
                autoComplete={mode === 'trial' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full h-10 pl-9 pr-3 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {mode === 'trial' && (
            <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={seedSampleData}
                onChange={(e) => setSeedSampleData(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600"
              />
              <span>Tạo sẵn dữ liệu đánh giá mẫu để trải nghiệm dashboard ngay</span>
            </label>
          )}

          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={submitting}
            className="w-full justify-center h-10"
          >
            {mode === 'trial' ? <Sparkles className="w-4 h-4" /> : <LogIn className="w-4 h-4" />}
            <span>
              {submitting
                ? 'Đang xử lý...'
                : mode === 'trial'
                ? 'Khởi tạo Workspace Dùng thử'
                : 'Đăng nhập'}
            </span>
          </Button>
        </form>

        <p className="text-[11px] text-center text-slate-400">
          Phiên làm việc được bảo vệ bằng JWT HttpOnly Cookie & phân quyền gian hàng.
        </p>
      </div>
    </div>
  );
}

// CreBy: MenBoyBMN
