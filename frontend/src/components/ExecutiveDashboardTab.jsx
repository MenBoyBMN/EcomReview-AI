import React, { useEffect, useState, useCallback } from 'react';
import {
  Building2,
  Star,
  AlertOctagon,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  ShoppingBag,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import { ASPECT_META } from '../constants/taxonomy';
import { Badge, Button } from './ui';

export default function ExecutiveDashboardTab({ onSelectShop, showToast }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadSummary = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.getExecutiveSummary();
      setSummary(res);
    } catch (err) {
      showToast?.(err.message || 'Không thể tải báo cáo tổng hợp Agency', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  if (loading && !summary) {
    return (
      <div className="py-12 text-center text-sm text-slate-400">
        Đang tổng hợp dữ liệu sức khỏe toàn chuỗi gian hàng...
      </div>
    );
  }

  const portfolio = summary?.portfolio || {};
  const channels = summary?.channel_summary || {};
  const shops = summary?.shops || [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Building2 className="w-5 h-5 text-indigo-600" />
            <span>Bảng Điều Hành Chuỗi Đa Gian Hàng (Agency Command)</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Xếp hạng các shop cần ưu tiên xử lý theo tỷ lệ phàn nàn, SLA CSKH và so sánh kênh bán hàng.
          </p>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={loadSummary} disabled={loading}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </Button>
      </div>

      {/* Portfolio KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="text-xs text-slate-500 dark:text-slate-400">Gian hàng đang vận hành</div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1 tabular-nums">
            {portfolio.total_shops || 0}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Tổng {Number(portfolio.total_reviews || 0).toLocaleString('vi-VN')} đánh giá
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <Star className="w-3.5 h-3.5 text-amber-500" />
            <span>Điểm TB toàn chuỗi</span>
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1 tabular-nums">
            {portfolio.portfolio_avg_rating || 0} ★
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Tính trọng số theo lượng đơn
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <AlertOctagon className="w-3.5 h-3.5 text-rose-500" />
            <span>Tỷ lệ phàn nàn chung</span>
          </div>
          <div className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1 tabular-nums">
            {portfolio.portfolio_neg_rate_pct || 0}%
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {portfolio.total_pending_actions || 0} hành động chờ duyệt
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>SLA CSKH (≤3★)</span>
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1 tabular-nums">
            {portfolio.portfolio_cskh_sla_pct ?? 100}%
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Còn {portfolio.total_pending_cskh || 0} đơn chưa gửi
          </div>
        </div>
      </div>

      {/* Shopee vs TikTok Portfolio Comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {['shopee', 'tiktok'].map((plat) => {
          const ch = channels[plat] || { reviews: 0, avg_rating: 0, neg_rate_pct: 0 };
          const isShopee = plat === 'shopee';
          return (
            <div
              key={plat}
              className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <ShoppingBag
                    className={`w-4 h-4 ${isShopee ? 'text-orange-500' : 'text-slate-900 dark:text-white'}`}
                  />
                  <span className="font-bold text-sm text-slate-900 dark:text-white">
                    {isShopee ? 'Shopee Toàn Chuỗi' : 'TikTok Shop Toàn Chuỗi'}
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {Number(ch.reviews || 0).toLocaleString('vi-VN')} đánh giá • Điểm TB:{' '}
                  <strong>{ch.avg_rating || 0}★</strong>
                </div>
              </div>
              <Badge tone={ch.neg_rate_pct >= 25 ? 'danger' : ch.neg_rate_pct >= 12 ? 'warning' : 'success'}>
                Tiêu cực {ch.neg_rate_pct || 0}%
              </Badge>
            </div>
          );
        })}
      </div>

      {/* Shop Ranking Table */}
      <div className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>Xếp Hạng Sức Khỏe Từng Gian Hàng (Ưu tiên rủi ro cao lên đầu)</span>
          </div>
        </div>

        {shops.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            Chưa có gian hàng nào được cấp quyền hoặc chưa có dữ liệu đánh giá.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 dark:bg-slate-800/70 text-slate-500 dark:text-slate-400 uppercase text-[11px]">
                <tr>
                  <th className="px-4 py-3">Gian hàng</th>
                  <th className="px-3 py-3 text-right">Đánh giá</th>
                  <th className="px-3 py-3 text-right">Điểm TB</th>
                  <th className="px-3 py-3 text-right">Tiêu cực</th>
                  <th className="px-3 py-3 text-right">SLA CSKH</th>
                  <th className="px-3 py-3">Vấn đề nổi bật</th>
                  <th className="px-3 py-3 text-right">Health Score</th>
                  <th className="px-4 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {shops.map((shop) => {
                  const painLabel = shop.top_pain_aspect
                    ? ASPECT_META[shop.top_pain_aspect]?.shortLabel || shop.top_pain_aspect
                    : 'Ổn định';
                  const scoreTone =
                    shop.health_score >= 80 ? 'success' : shop.health_score >= 60 ? 'warning' : 'danger';
                  return (
                    <tr
                      key={shop.slug}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900 dark:text-white">{shop.name}</div>
                        <div className="text-[11px] text-slate-400">
                          {shop.slug} • Shopee: {shop.shopee_reviews} | TikTok: {shop.tiktok_reviews}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-medium">
                        {shop.total_reviews}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{shop.avg_rating} ★</td>
                      <td className="px-3 py-3 text-right tabular-nums">
                        <span className={shop.negative_rate_pct >= 25 ? 'text-rose-600 font-semibold' : ''}>
                          {shop.negative_rate_pct}%
                        </span>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">
                        {shop.cskh_sla_pct}% ({shop.pending_cskh} tồn)
                      </td>
                      <td className="px-3 py-3">
                        <Badge tone={shop.top_pain_aspect ? 'warning' : 'neutral'}>{painLabel}</Badge>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <Badge tone={scoreTone}>{shop.health_score}/100</Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onSelectShop?.(shop.slug)}
                        >
                          <span>Mở shop</span>
                          <ArrowRight className="w-3 h-3" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// CreBy: MenBoyBMN
