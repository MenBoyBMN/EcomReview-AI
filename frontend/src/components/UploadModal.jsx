import React, { useEffect, useState } from 'react';
import { UploadCloud, Sparkles, ShieldCheck, FileSpreadsheet } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Button } from './ui';

export default function UploadModal({
  isOpen,
  onClose,
  scenarioTag,
  onSuccess,
  showToast,
}) {
  const [uploadTab, setUploadTab] = useState('single'); // 'single' | 'file'
  const [platform, setPlatform] = useState('shopee');
  const [shop, setShop] = useState('shop_aomua');
  const [product, setProduct] = useState('ao_mua_da_ca');
  const [rating, setRating] = useState(4);
  const [reviewId, setReviewId] = useState(
    () => `usr_${Math.floor(1000 + Math.random() * 9000)}`
  );
  const [text, setText] = useState(
    'Áo mưa vải dù dày dặn đẹp lắm shop ơi, nhưng đi mưa to nước vẫn hơi thấm nhẹ ở đường may đáy quần. SĐT mình 0912345678 nhé.'
  );
  const [analyzerMethod, setAnalyzerMethod] = useState('b1_rule');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadReport, setUploadReport] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setUploadReport(null);
      setSelectedFile(null);
    }
  }, [isOpen]);

  const handleFilePick = (file) => {
    if (!file) return;
    const lower = (file.name || '').toLowerCase();
    if (!lower.endsWith('.csv') && !lower.endsWith('.xlsx')) {
      showToast('Chỉ hỗ trợ tệp định dạng .csv hoặc .xlsx.', 'error');
      return;
    }
    setSelectedFile(file);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setUploadReport(null);

      if (uploadTab === 'file') {
        if (!selectedFile) {
          showToast('Vui lòng chọn tệp .csv hoặc .xlsx để tải lên.', 'error');
          return;
        }
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('scenario_tag', scenarioTag);
        formData.append('analyzer_method', analyzerMethod);
        formData.append('platform', platform);
        formData.append('shop', shop.trim() || 'shop_aomua');
        formData.append('product', product.trim() || 'ao_mua_da_ca');

        const res = await api.uploadReviewFile(formData);
        setUploadReport(res);
        showToast(
          `Đã nạp ${res.inserted_count} đánh giá từ tệp` +
            (res.skipped_count > 0 ? ` (bỏ qua ${res.skipped_count} dòng lỗi)` : '!'),
          'success'
        );
        setSelectedFile(null);
        onSuccess();
        if (!res.skipped_count) onClose();
        return;
      }

      if (!text.trim()) return;
      const payload = {
        scenario_tag: scenarioTag,
        analyzer_method: analyzerMethod,
        reviews: [
          {
            review_id: reviewId.trim() || `usr_${Date.now()}`,
            platform,
            shop: shop.trim() || 'shop_aomua',
            product: product.trim() || 'ao_mua_da_ca',
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
        <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-100 dark:bg-slate-800/80">
          <button
            type="button"
            onClick={() => setUploadTab('single')}
            className={`py-2 px-3 rounded-lg text-xs font-semibold transition ${
              uploadTab === 'single'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            Nhập 1 đánh giá
          </button>
          <button
            type="button"
            onClick={() => setUploadTab('file')}
            className={`py-2 px-3 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 ${
              uploadTab === 'file'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                : 'text-slate-600 dark:text-slate-400'
            }`}
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Tải file CSV / Excel</span>
          </button>
        </div>

        <div className="p-3 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/60 flex items-start gap-2.5 text-xs text-indigo-800 dark:text-indigo-300 leading-relaxed">
          <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5 text-indigo-600" />
          <span>
            Hệ thống sẽ tự động ẩn số điện thoại / email cá nhân, chuẩn hóa từ viết tắt tiếng Việt và bóc tách cảm xúc theo 8 khía cạnh.
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Tên gian hàng (Shop)
            </label>
            <input
              type="text"
              value={shop}
              onChange={(e) => setShop(e.target.value)}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Mã / Tên sản phẩm
            </label>
            <input
              type="text"
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
          </div>
        </div>

        {uploadTab === 'file' ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Sàn mặc định (nếu file thiếu cột)
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
                  Phương thức phân tích
                </label>
                <select
                  value={analyzerMethod}
                  onChange={(e) => setAnalyzerMethod(e.target.value)}
                  className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                >
                  <option value="b1_rule">Bộ từ điển tiếng Việt (Tức thì)</option>
                  <option value="a1_gemini_v2">AI Gemini Flash</option>
                  <option value="a1_ollama">AI Local Ollama</option>
                </select>
              </div>
            </div>

            <label
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                handleFilePick(e.dataTransfer?.files?.[0]);
              }}
              className={`flex flex-col items-center justify-center p-5 rounded-xl border-2 border-dashed cursor-pointer transition ${
                isDragging
                  ? 'border-indigo-500 bg-indigo-50/70 dark:bg-indigo-950/40'
                  : 'border-slate-300 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800/40 hover:border-indigo-400'
              }`}
            >
              <FileSpreadsheet className="w-7 h-7 text-indigo-500 mb-1.5" />
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 text-center">
                {selectedFile
                  ? selectedFile.name
                  : 'Kéo-thả hoặc bấm chọn tệp .csv / .xlsx (tối đa 5 MB, 1000 dòng)'}
              </span>
              <span className="text-[11px] text-slate-400 mt-1 text-center">
                Hỗ trợ cột: review_id / mã đơn hàng, rating / số sao, text / bình luận
              </span>
              <input
                type="file"
                accept=".csv,.xlsx"
                className="hidden"
                onChange={(e) => {
                  handleFilePick(e.target.files?.[0]);
                  e.target.value = '';
                }}
              />
            </label>

            {uploadReport && uploadReport.skipped_count > 0 && (
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 space-y-1">
                <div className="font-semibold">
                  Đã nạp {uploadReport.inserted_count} dòng • Bỏ qua {uploadReport.skipped_count} dòng lỗi:
                </div>
                <ul className="list-disc pl-4 space-y-0.5 max-h-24 overflow-y-auto">
                  {uploadReport.skipped_rows?.map((sr, i) => (
                    <li key={i}>
                      Dòng {sr.row}: {sr.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <>
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
                <option value="a1_ollama">Mô hình AI Local Ollama</option>
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
          </>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" size="md" onClick={onClose}>
            Hủy
          </Button>
          <Button type="submit" variant="primary" size="md" disabled={submitting}>
            <Sparkles className="w-4 h-4" />
            <span>
              {submitting
                ? 'Đang lưu & phân tích...'
                : uploadTab === 'file'
                ? 'Tải lên & phân tích hàng loạt'
                : 'Thêm & phân tích ngay'}
            </span>
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// CreBy: MenBoyBMN
