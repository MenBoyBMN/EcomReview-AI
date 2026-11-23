import React, { useEffect, useState } from 'react';
import { BellRing, Send, Save } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Button } from './ui';

export default function AlertSettingsModal({
  isOpen,
  onClose,
  scenarioTag,
  shopInfo,
  onSaved,
  showToast,
}) {
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [minRatingAlert, setMinRatingAlert] = useState(2);
  const [enableCritical, setEnableCritical] = useState(true);
  const [enableZtest, setEnableZtest] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const cfg = shopInfo?.alert_config || {};
      setTelegramToken('');
      setTelegramChatId(cfg.telegram_chat_id || '');
      setWebhookUrl(cfg.webhook_url || '');
      setMinRatingAlert(Number(cfg.min_rating_alert ?? 2));
      setEnableCritical(cfg.enable_critical_review_alert !== false);
      setEnableZtest(cfg.enable_ztest_alert !== false);
    }
  }, [isOpen, shopInfo]);

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      await api.updateShopAlerts(scenarioTag, {
        ...(telegramToken.trim() ? { telegram_bot_token: telegramToken.trim() } : {}),
        telegram_chat_id: telegramChatId.trim(),
        webhook_url: webhookUrl.trim(),
        min_rating_alert: Number(minRatingAlert),
        enable_critical_review_alert: enableCritical,
        enable_ztest_alert: enableZtest,
      });
      if (showToast) {
        showToast('Đã lưu cấu hình cảnh báo chủ động cho gian hàng!', 'success');
      }
      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      if (showToast) {
        showToast(err.message || 'Không thể lưu cấu hình cảnh báo', 'error');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    try {
      setTesting(true);
      const res = await api.testShopAlerts(scenarioTag);
      const sent = (res.results || []).filter((r) => r.status === 'SENT').length;
      if (showToast) {
        showToast(
          sent > 0
            ? `Đã gửi thành công ${sent} tin nhắn thử nghiệm!`
            : 'Đã gửi thử nhưng kênh báo lỗi. Vui lòng kiểm tra lại Token / Chat ID / URL.',
          sent > 0 ? 'success' : 'error'
        );
      }
    } catch (err) {
      if (showToast) {
        showToast(err.message || 'Gửi thử cảnh báo thất bại', 'error');
      }
    } finally {
      setTesting(false);
    }
  };

  const tokenConfigured = Boolean(shopInfo?.alert_config?.telegram_bot_token_configured);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={BellRing}
      title="Cảnh báo chủ động (Telegram & Webhook)"
      subtitle={`Cấu hình bắn thông báo tự động cho gian hàng ${shopInfo?.name || scenarioTag}`}
      maxWidth="max-w-lg"
    >
      <form onSubmit={handleSave} className="space-y-4 text-sm">
        <div className="space-y-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
          <div className="text-xs font-bold text-slate-800 dark:text-slate-100">
            1. Kênh Telegram Bot (Khuyến nghị cho Chủ shop)
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Telegram Bot Token {tokenConfigured ? '(Đã cấu hình — bỏ trống nếu giữ nguyên)' : ''}
            </label>
            <input
              type="password"
              value={telegramToken}
              onChange={(e) => setTelegramToken(e.target.value)}
              placeholder={tokenConfigured ? '••••••••••••••••' : '123456:ABC-DEF...'}
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Telegram Chat ID / Group ID
            </label>
            <input
              type="text"
              value={telegramChatId}
              onChange={(e) => setTelegramChatId(e.target.value)}
              placeholder="-1001234567890"
              className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
            />
          </div>
        </div>

        <div className="space-y-2 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
          <div className="text-xs font-bold text-slate-800 dark:text-slate-100">
            2. Webhook tích hợp Zalo OA / Lark / Slack / n8n (Tùy chọn)
          </div>
          <input
            type="url"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://hooks.example.com/ecomreview"
            className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enableCritical}
              onChange={(e) => setEnableCritical(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600"
            />
            <span>Báo ngay khi có đánh giá tiêu cực (≤ {minRatingAlert}★)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enableZtest}
              onChange={(e) => setEnableZtest(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600"
            />
            <span>Báo khi Z-test phát hiện đột biến lỗi</span>
          </label>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Ngưỡng sao kích hoạt cảnh báo khẩn
          </label>
          <select
            value={minRatingAlert}
            onChange={(e) => setMinRatingAlert(Number(e.target.value))}
            className="w-full h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value={1}>Chỉ báo đánh giá 1 sao</option>
            <option value={2}>Báo đánh giá 1–2 sao (Khuyến nghị)</option>
            <option value={3}>Báo đánh giá từ 3 sao trở xuống</option>
          </select>
        </div>

        <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={testing}
            onClick={handleTest}
          >
            <Send className="w-3.5 h-3.5" />
            <span>{testing ? 'Đang gửi thử...' : 'Gửi tin thử nghiệm'}</span>
          </Button>
          <div className="flex items-center gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={onClose}>
              Đóng
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={saving}>
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Đang lưu...' : 'Lưu cấu hình'}</span>
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

// CreBy: MenBoyBMN
