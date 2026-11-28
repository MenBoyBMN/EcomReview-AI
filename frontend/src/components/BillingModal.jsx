import React, { useEffect, useState } from 'react';
import { CreditCard, AlertTriangle, CheckCircle2, Gauge } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Badge, Button } from './ui';

export default function BillingModal({ isOpen, onClose, scenarioTag, showToast }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    api
      .getBillingUsage('', '')
      .then((res) => setData(res))
      .catch((err) => showToast?.(err.message || 'Không tải được thông tin gói cước', 'error'))
      .finally(() => setLoading(false));
  }, [isOpen, scenarioTag, showToast]);

  const sub = data?.subscription || {};
  const usage = data?.usage || {};
  const plans = data?.plans || [];
  const llmPct = Math.min(100, Number(usage.llm_usage_pct || 0));

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={CreditCard}
      title="Gói Cước & Hạn Mức Sử Dụng (Metering)"
      subtitle={`Chu kỳ tháng ${data?.month_key || 'hiện tại'} • Chính sách vượt ngưỡng: ${
        sub.overage_policy === 'block' ? 'Tạm chặn AI' : 'Tự động chuyển B1 Rule (Không gián đoạn)'
      }`}
      maxWidth="max-w-2xl"
    >
      {loading ? (
        <div className="py-8 text-center text-xs text-slate-400">Đang tải dữ liệu gói cước...</div>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Gauge className="w-4 h-4 text-indigo-600" />
                <span className="font-bold text-slate-900 dark:text-white uppercase">
                  Gói {sub.plan_code || 'basic'}
                </span>
                <Badge tone={sub.status === 'ACTIVE' ? 'success' : sub.status === 'TRIAL' ? 'info' : 'danger'}>
                  {sub.status || 'ACTIVE'}
                </Badge>
              </div>
              {sub.trial_ends_at && (
                <span className="text-xs text-slate-500">
                  Hết hạn dùng thử: {String(sub.trial_ends_at).slice(0, 10)}
                </span>
              )}
            </div>

            {(usage.is_near_limit || usage.is_over_limit) && (
              <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-center gap-2 text-xs text-amber-800 dark:text-amber-300">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>
                  {usage.is_over_limit
                    ? 'Đã chạm hạn mức phân tích LLM tháng này — hệ thống đang tự chạy chế độ B1 Rule để bảo vệ vận hành.'
                    : 'Mức sử dụng LLM đã vượt 80% hạn mức tháng. Hãy cân nhắc nâng cấp gói Pro hoặc Agency.'}
                </span>
              </div>
            )}

            <div className="space-y-2 text-xs">
              <div>
                <div className="flex justify-between font-medium mb-1">
                  <span>Đánh giá phân tích AI (LLM)</span>
                  <span className="tabular-nums">
                    {usage.llm_reviews_used || 0} / {sub.monthly_llm_review_limit || 2000} ({llmPct}%)
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      llmPct >= 100 ? 'bg-rose-500' : llmPct >= 80 ? 'bg-amber-500' : 'bg-indigo-600'
                    }`}
                    style={{ width: `${llmPct}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-1 text-center">
                <div className="p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-[11px] text-slate-500">Gian hàng</div>
                  <div className="font-bold text-slate-900 dark:text-white">
                    {usage.shops_used || 0} / {sub.max_shops || 2}
                  </div>
                </div>
                <div className="p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-[11px] text-slate-500">Nhân sự</div>
                  <div className="font-bold text-slate-900 dark:text-white">
                    {usage.users_used || 0} / {sub.max_users || 3}
                  </div>
                </div>
                <div className="p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
                  <div className="text-[11px] text-slate-500">Nháp CSKH / B1</div>
                  <div className="font-bold text-slate-900 dark:text-white">
                    {usage.replies_generated || 0} / {usage.rule_reviews_used || 0}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {plans.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {plans.map((p) => {
                const isCurrent = p.plan_code === sub.plan_code;
                return (
                  <div
                    key={p.plan_code}
                    className={`p-3 rounded-xl border ${
                      isCurrent
                        ? 'border-indigo-500 bg-indigo-50/60 dark:bg-indigo-950/30'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-xs text-slate-900 dark:text-white">
                        {p.display_name}
                      </span>
                      {isCurrent && <CheckCircle2 className="w-4 h-4 text-indigo-600" />}
                    </div>
                    <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 mt-1">
                      {p.price_vnd_month > 0
                        ? `${Number(p.price_vnd_month).toLocaleString('vi-VN')}đ / tháng`
                        : 'Miễn phí 14 ngày'}
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1">
                      {p.monthly_llm_review_limit.toLocaleString('vi-VN')} review LLM • {p.max_shops} shop • {p.max_users} user
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] text-slate-500">
              Cần nâng hạn mức Agency / xuất hóa đơn VAT? Liên hệ đội ngũ kinh doanh EcomReview AI.
            </span>
            <Button type="button" variant="secondary" size="sm" onClick={onClose}>
              Đóng
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// CreBy: MenBoyBMN
