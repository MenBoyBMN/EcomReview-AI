import React, { useState } from 'react';
import { UploadCloud, Sparkles, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Button } from './ui';

export default function UploadModal({
  isOpen,
  onClose,
  scenarioTag,
  onSuccess,
  showToast,
}) {
  const [platform, setPlatform] = useState('shopee');
  const [rating, setRating] = useState(4);
  const [reviewId, setReviewId] = useState(
    () => `usr_${Math.floor(1000 + Math.random() * 9000)}`
  );
  const [text, setText] = useState(
    'Áo mưa vải dù dày dặn đẹp lắm shop ơi, nhưng đi mưa to nước vẫn hơi thấm nhẹ ở đường may đáy quần. SĐT mình 0912345678 nhé.'
  );
  const [analyzerMethod, setAnalyzerMethod] = useState('b1_rule');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try {
      setSubmitting(true);
      const payload = {
        scenario_tag: scenarioTag,
        analyzer_method: analyzerMethod,
        reviews: [
          {
            review_id: reviewId.trim() || `usr_${Date.now()}`,
            platform,
            shop: 'shop_aomua',
            product: 'ao_mua_da_ca',
            rating: Number(rating),
            text: text.trim(),
            created_at: new Date().toISOString().slice(0, 10),
          },
        ],
      };

      const res = await api.uploadReviews(payload);
      showToast(
        `Đã thêm và phân tích thành công ${res.inserted_count} đánh giá mới!`,
        'success'
      );
      setReviewId(`usr_${Math.floor(1000 + Math.random() * 9000)}`);
      onSuccess();
      onClose();
    } catch (err) {
      showToast(err.message || 'Không thể thêm đánh giá mới', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={UploadCloud}
      title="Thêm đánh giá khách hàng mới"
      subtitle={`Dữ liệu sẽ được lưu vào bộ kịch bản ${scenarioTag}`}
      maxWidth="max-w-lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-sm">
        <div className="p-3 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/60 flex items-start gap-2.5 text-xs text-indigo-800 dark:text-indigo-300 leading-relaxed">
          <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5 text-indigo-600" />
          <span>
            Hệ thống sẽ tự động ẩn số điện thoại / email cá nhân, chuẩn hóa từ viết tắt tiếng Việt và bóc tách cảm xúc theo 8 khía cạnh.
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Mã đánh giá
            </label>
            <input
              type="text"
              required
              value={reviewId}
              onChange={(e) => setReviewId(e.target.value)}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Sàn thương mại
            </label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            >
              <option value="shopee">Shopee</option>
              <option value="tiktok">TikTok Shop</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Điểm đánh giá
            </label>
            <select
              value={rating}
              onChange={(e) => setRating(Number(e.target.value))}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            >
              <option value={5}>5 sao ★★★★★</option>
              <option value={4}>4 sao ★★★★</option>
              <option value={3}>3 sao ★★★</option>
              <option value={2}>2 sao ★★</option>
              <option value={1}>1 sao ★</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Phương thức phân tích
          </label>
          <select
            value={analyzerMethod}
            onChange={(e) => setAnalyzerMethod(e.target.value)}
            className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="b1_rule">Bộ từ điển tiếng Việt (Tức thì & không cần mạng)</option>
            <option value="a1_gemini_v2">Mô hình AI Gemini Flash (Phân tích chuyên sâu)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Nội dung bình luận của khách hàng
          </label>
          <textarea
            rows={4}
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Nhập nội dung đánh giá tiếng Việt của khách hàng..."
            className="w-full p-3 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 leading-relaxed"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" size="md" onClick={onClose}>
            Hủy
          </Button>
          <Button type="submit" variant="primary" size="md" disabled={submitting}>
            <Sparkles className="w-4 h-4" />
            <span>{submitting ? 'Đang lưu & phân tích...' : 'Thêm & phân tích ngay'}</span>
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// CreBy: MenBoyBMN
