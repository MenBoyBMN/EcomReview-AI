import React, { useEffect, useState, useCallback } from 'react';
import { BellRing, Send, Save, Link2, RefreshCw, Unlink, CalendarClock } from 'lucide-react';
import { api } from '../api/client';
import { Modal, Button, Badge } from './ui';

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
  const [webhookFormat, setWebhookFormat] = useState('generic');
  const [zaloRecipientId, setZaloRecipientId] = useState('');
  const [weeklyDigestEnabled, setWeeklyDigestEnabled] = useState(false);
  const [minRatingAlert, setMinRatingAlert] = useState(2);
  const [enableCritical, setEnableCritical] = useState(true);
  const [enableZtest, setEnableZtest] = useState(true);
  const [industry, setIndustry] = useState('raincoat');
  const [industries, setIndustries] = useState([]);
  const [shopSignature, setShopSignature] = useState('');
  const [tone, setTone] = useState('');
  const [returnPolicy, setReturnPolicy] = useState('');
  const [cskhNotes, setCskhNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [sendingDigest, setSendingDigest] = useState(false);
  const [connectors, setConnectors] = useState({});
  const [busyPlatform, setBusyPlatform] = useState(null);

  const loadConnectors = useCallback(async () => {
    try {
      const res = await api.getShopConnectors(scenarioTag);
      setConnectors(res?.platforms || {});
    } catch {
      setConnectors({});
    }
  }, [scenarioTag]);

  useEffect(() => {
    if (isOpen) {
      const cfg = shopInfo?.alert_config || {};
      const bv = cfg.brand_voice || {};
      setTelegramToken('');
      setTelegramChatId(cfg.telegram_chat_id || '');
      setWebhookUrl(cfg.webhook_url || '');
      setWebhookFormat(cfg.webhook_format || 'generic');
      setZaloRecipientId(cfg.zalo_oa_recipient_id || '');
      setWeeklyDigestEnabled(Boolean(cfg.weekly_digest_enabled));
      setMinRatingAlert(Number(cfg.min_rating_alert ?? 2));
      setEnableCritical(cfg.enable_critical_review_alert !== false);
      setEnableZtest(cfg.enable_ztest_alert !== false);
      setIndustry(shopInfo?.industry || 'raincoat');
      setShopSignature(bv.shop_signature || '');
      setTone(bv.tone || '');
      setReturnPolicy(bv.return_policy || '');
      setCskhNotes(bv.cskh_notes || '');
      loadConnectors();
      api
        .getIndustries()
        .then((res) => setIndustries(res?.industries || []))
        .catch(() => setIndustries([]));
    }
  }, [isOpen, shopInfo, loadConnectors]);

  const handleOAuthConnect = async (platform) => {
    try {
      setBusyPlatform(platform);
      const redirectUrl = `${window.location.origin}/api/v1/integrations/oauth/${platform}/callback`;
      const res = await api.authorizeShopConnector(scenarioTag, platform, redirectUrl);
      if (res?.auth_url) {
        window.open(res.auth_url, '_blank', 'noopener,noreferrer');
        showToast?.(`Đã mở trang ủy quyền ${platform.toUpperCase()} ở tab mới.`, 'info');
      }
    } catch (err) {
      showToast?.(err.message || `Chưa cấu hình Partner App cho ${platform}`, 'error');
    } finally {
      setBusyPlatform(null);
    }
  };

  const handleSyncNow = async (platform) => {
    try {
      setBusyPlatform(platform);
      const res = await api.syncShopConnector(scenarioTag, platform, {});
      showToast?.(
        `Đã đưa lệnh đồng bộ ${platform.toUpperCase()} vào hàng đợi (#${res.job_id}).`,
        'success'
      );
      await loadConnectors();
      if (onSaved) onSaved();
    } catch (err) {
      showToast?.(err.message || `Đồng bộ ${platform} thất bại`, 'error');
    } finally {
      setBusyPlatform(null);
    }
  };

  const handleDisconnect = async (platform) => {
    try {
      setBusyPlatform(platform);
      await api.disconnectShopConnector(scenarioTag, platform);
      showToast?.(`Đã ngắt kết nối ${platform.toUpperCase()}.`, 'info');
      await loadConnectors();
    } catch (err) {
      showToast?.(err.message || `Không thể ngắt kết nối ${platform}`, 'error');
    } finally {
      setBusyPlatform(null);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      await api.updateShopAlerts(scenarioTag, {
        ...(telegramToken.trim() ? { telegram_bot_token: telegramToken.trim() } : {}),
        telegram_chat_id: telegramChatId.trim(),
        webhook_url: webhookUrl.trim(),
        webhook_format: webhookFormat,
        zalo_oa_recipient_id: zaloRecipientId.trim(),
        weekly_digest_enabled: weeklyDigestEnabled,
        min_rating_alert: Number(minRatingAlert),
        enable_critical_review_alert: enableCritical,
        enable_ztest_alert: enableZtest,
      });
      await api.updateShopProfile(scenarioTag, {
        industry,
        shop_signature: shopSignature.trim(),
        tone: tone.trim(),
        return_policy: returnPolicy.trim(),
        cskh_notes: cskhNotes.trim(),
      });
      if (showToast) {
        showToast('Đã lưu cấu hình cảnh báo, ngành hàng và Brand Voice cho gian hàng!', 'success');
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

  const handleSendDigest = async () => {
    try {
      setSendingDigest(true);
      const res = await api.sendWeeklyDigest(scenarioTag, { force: true, previewOnly: false });
      const sent = (res?.dispatches || []).filter((r) => r.status === 'SENT').length;
      showToast?.(
        sent > 0
          ? `Đã gửi Báo cáo tuần ${res?.digest?.week_key || ''} qua ${sent} kênh!`
          : 'Đã tạo bản tin tuần nhưng chưa có kênh Telegram/Webhook để gửi.',
        sent > 0 ? 'success' : 'info'
      );
    } catch (err) {
      showToast?.(err.message || 'Gửi báo cáo tuần thất bại', 'error');
    } finally {
      setSendingDigest(false);
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
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                Định dạng Webhook
              </label>
              <select
                value={webhookFormat}
                onChange={(e) => setWebhookFormat(e.target.value)}
                className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
              >
                <option value="generic">Generic JSON (n8n / Custom)</option>
                <option value="lark">Lark / Feishu Card</option>
                <option value="slack">Slack Block Kit</option>
                <option value="zalo_oa">Zalo OA / ZNS Webhook</option>
              </select>
            </div>
            {webhookFormat === 'zalo_oa' && (
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Zalo OA User / Recipient ID
                </label>
                <input
                  type="text"
                  value={zaloRecipientId}
                  onChange={(e) => setZaloRecipientId(e.target.value)}
                  placeholder="zalo_uid_..."
                  className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
                />
              </div>
            )}
          </div>
          <label className="flex items-center gap-2 cursor-pointer text-xs pt-1">
            <input
              type="checkbox"
              checked={weeklyDigestEnabled}
              onChange={(e) => setWeeklyDigestEnabled(e.target.checked)}
              className="rounded border-slate-300 text-indigo-600"
            />
            <span>Tự động gửi Báo cáo tổng hợp tuần vào sáng Thứ 2 (Weekly Digest)</span>
          </label>
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

        <div className="space-y-2.5 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
          <div className="text-xs font-bold text-slate-800 dark:text-slate-100">
            3. Kết nối Sàn 2 chiều (Tự kéo đánh giá & Đẩy phản hồi CSKH)
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {['shopee', 'tiktok'].map((plat) => {
              const conn = connectors[plat];
              const isBusy = busyPlatform === plat;
              const label = plat === 'shopee' ? 'Shopee' : 'TikTok Shop';
              return (
                <div
                  key={plat}
                  className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-100">
                      {label}
                    </span>
                    <Badge tone={conn ? 'success' : 'neutral'}>
                      {conn ? 'Đã kết nối' : 'Chưa kết nối'}
                    </Badge>
                  </div>
                  {conn ? (
                    <>
                      <div className="text-[11px] text-slate-500 truncate">
                        Shop ID: {conn.external_shop_id} •{' '}
                        {conn.last_synced_at
                          ? `Sync: ${String(conn.last_synced_at).slice(0, 16).replace('T', ' ')}`
                          : 'Chưa đồng bộ'}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={isBusy}
                          onClick={() => handleSyncNow(plat)}
                        >
                          <RefreshCw className="w-3 h-3" />
                          <span>Đồng bộ</span>
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={isBusy}
                          onClick={() => handleDisconnect(plat)}
                        >
                          <Unlink className="w-3 h-3 text-rose-500" />
                          <span>Ngắt</span>
                        </Button>
                      </div>
                    </>
                  ) : (
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isBusy}
                      onClick={() => handleOAuthConnect(plat)}
                    >
                      <Link2 className="w-3 h-3 text-indigo-600" />
                      <span>Kết nối OAuth {label}</span>
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-2.5 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700">
          <div className="text-xs font-bold text-slate-800 dark:text-slate-100">
            4. Ngành hàng (Playbook) & Giọng văn thương hiệu (Brand Voice)
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                Mẫu ngành hàng
              </label>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
              >
                {(industries.length > 0
                  ? industries
                  : [
                      { industry: 'raincoat', display_name: 'Áo mưa & Đồ đi mưa' },
                      { industry: 'fashion', display_name: 'Thời trang & May mặc' },
                      { industry: 'cosmetics', display_name: 'Mỹ phẩm & Chăm sóc da' },
                      { industry: 'home_living', display_name: 'Gia dụng & Đời sống' },
                      { industry: 'electronics', display_name: 'Phụ kiện & Điện tử' },
                    ]
                ).map((item) => (
                  <option key={item.industry} value={item.industry}>
                    {item.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                Xưng hô / Tên Shop khi CSKH
              </label>
              <input
                type="text"
                value={shopSignature}
                onChange={(e) => setShopSignature(e.target.value)}
                placeholder="VD: Lumina Beauty Official"
                className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input
              type="text"
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              placeholder="Giọng điệu (VD: Thân thiện, chuyên gia)"
              className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
            />
            <input
              type="text"
              value={returnPolicy}
              onChange={(e) => setReturnPolicy(e.target.value)}
              placeholder="Chính sách đổi trả (VD: Hỗ trợ đổi 1-1 trong 7 ngày)"
              className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
            />
          </div>
          <input
            type="text"
            value={cskhNotes}
            onChange={(e) => setCskhNotes(e.target.value)}
            placeholder="Lưu ý vận hành/CSKH riêng cho AI Planner & Reply..."
            className="w-full h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
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
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={sendingDigest}
              onClick={handleSendDigest}
            >
              <CalendarClock className="w-3.5 h-3.5" />
              <span>{sendingDigest ? 'Đang gửi tuần...' : 'Gửi Digest tuần'}</span>
            </Button>
          </div>
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
