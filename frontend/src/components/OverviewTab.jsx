import React, { useEffect, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  MessageSquare,
  Star,
  AlertTriangle,
  EyeOff,
  TrendingUp,
  Scale,
  Calendar,
} from 'lucide-react';
import { api } from '../api/client';
import { ASPECT_META, getAspectLabel, getAspectShortLabel } from '../constants/taxonomy';
import { Card, SectionHeader, StatCard, Badge, InfoTip, EmptyState } from './ui';
import AspectHealthList from './AspectHealthList';

export default function OverviewTab({
  overview,
  scenarioTag,
  loadingOverview,
  darkMode,
  onNavigateReviewsWithAspect,
}) {
  const [trendPeriod, setTrendPeriod] = useState('month');
  const [trendAspect, setTrendAspect] = useState('');
  const [trends, setTrends] = useState([]);
  const [loadingTrends, setLoadingTrends] = useState(false);

  useEffect(() => {
    let active = true;
    setLoadingTrends(true);
    api
      .getTrends(scenarioTag, trendPeriod, trendAspect, 2)
      .then((res) => {
        if (active) {
          const normalized = (res.trends || []).map((d) => ({
            ...d,
            pos_pct:
              d.pos_pct !== undefined
                ? d.pos_pct
                : d.total > 0
                ? Number(((Number(d.pos_count || 0) / d.total) * 100).toFixed(1))
                : 0,
          }));
          setTrends(normalized);
        }
      })
      .catch(() => {
        if (active) setTrends([]);
      })
      .finally(() => {
        if (active) setLoadingTrends(false);
      });
    return () => {
      active = false;
    };
  }, [scenarioTag, trendPeriod, trendAspect]);

  if (loadingOverview || !overview) {
    return (
      <div className="space-y-5 animate-pulse">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((k) => (
            <div
              key={k}
              className="h-32 rounded-2xl bg-slate-200/70 dark:bg-slate-800/60"
            />
          ))}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          <div className="xl:col-span-7 h-80 rounded-2xl bg-slate-200/70 dark:bg-slate-800/60" />
          <div className="xl:col-span-5 h-80 rounded-2xl bg-slate-200/70 dark:bg-slate-800/60" />
        </div>
      </div>
    );
  }

  const {
    total_reviews = 0,
    avg_rating = 0,
    positive_reviews = 0,
    negative_reviews = 0,
    negative_rate_pct = 0,
    negative_ci_95 = [0, 0],
    platform_counts = { shopee: 0, tiktok: 0 },
    aspect_stats = [],
    platform_comparison = [],
    hidden_complaints = {},
  } = overview;

  const posRatePct =
    total_reviews > 0 ? ((positive_reviews / total_reviews) * 100).toFixed(1) : '0.0';

  const axisColor = darkMode ? '#94A3B8' : '#64748B';
  const gridColor = darkMode ? '#334155' : '#E2E8F0';

  return (
    <div className="space-y-5">
      {/* Row 1: 4 Executive KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Tổng lượt đánh giá"
          value={total_reviews.toLocaleString('vi-VN')}
          unit="đánh giá"
          icon={MessageSquare}
          tone="indigo"
          footer={
            <div className="flex items-center gap-2 flex-wrap">
              <span className="badge-shopee">Shopee: {platform_counts.shopee || 0}</span>
              <span className="badge-tiktok">TikTok: {platform_counts.tiktok || 0}</span>
            </div>
          }
        />

        <StatCard
          label="Điểm sao trung bình"
          value={avg_rating.toFixed(2)}
          unit="/ 5.0 ★"
          icon={Star}
          tone="emerald"
          footer={
            <div className="flex items-center justify-between gap-2 text-slate-600 dark:text-slate-300">
              <span className="shrink-0">Khách hài lòng:</span>
              <strong className="text-emerald-600 dark:text-emerald-400 tabular-nums whitespace-nowrap">
                {posRatePct}% ({positive_reviews} bài)
              </strong>
            </div>
          }
        />

        <StatCard
          label="Tỷ lệ phàn nàn"
          value={`${negative_rate_pct}%`}
          unit={`(${negative_reviews} bài)`}
          tooltip={`Khoảng tin cậy thống kê Wilson 95%: từ ${negative_ci_95[0]}% đến ${negative_ci_95[1]}%. Số liệu được tính trực tiếp từ cơ sở dữ liệu.`}
          icon={AlertTriangle}
          tone="rose"
          footer={
            <div className="flex items-center justify-between gap-2 text-slate-500 dark:text-slate-400">
              <span className="shrink-0">Ước lượng 95%:</span>
              <span className="font-semibold text-slate-700 dark:text-slate-200 tabular-nums whitespace-nowrap">
                {negative_ci_95[0]}% – {negative_ci_95[1]}%
              </span>
            </div>
          }
        />

        <StatCard
          label="Phàn nàn ẩn (4–5★)"
          value={hidden_complaints.hidden_count || 0}
          unit={`/ ${hidden_complaints.high_rating_total || 0} bài 4–5★`}
          tooltip="Các đánh giá khách chấm 4 hoặc 5 sao nhưng nội dung bình luận lại nhắc tới nhược điểm của sản phẩm."
          icon={EyeOff}
          tone="amber"
          footer={
            <div className="flex items-center justify-between gap-2 text-slate-500 dark:text-slate-400">
              <span className="shrink-0">Vấn đề ẩn chính:</span>
              <strong className="text-amber-700 dark:text-amber-300 truncate">
                {hidden_complaints.top_hidden_aspects?.[0]
                  ? getAspectShortLabel(hidden_complaints.top_hidden_aspects[0].aspect)
                  : 'Không có'}
              </strong>
            </div>
          }
        />
      </div>

      {/* Row 2: Aspect Health List + Sentiment Trend */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        {/* Left: 8 Aspects Health List */}
        <Card className="xl:col-span-7">
          <SectionHeader
            title="Khách hàng đánh giá từng khía cạnh thế nào?"
            subtitle="Xếp hạng từ khía cạnh bị phàn nàn nhiều nhất đến ít nhất để ưu tiên cải thiện"
          />
          <AspectHealthList
            aspectStats={aspect_stats}
            onSelectAspect={onNavigateReviewsWithAspect}
          />
        </Card>

        {/* Right: Historical Sentiment Trend */}
        <Card className="xl:col-span-5 space-y-4">
          <div className="space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <TrendingUp className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <h2 className="text-base font-semibold text-slate-900 dark:text-white truncate">
                  Xu hướng theo thời gian
                </h2>
              </div>

              <div className="inline-flex rounded-lg bg-slate-100 dark:bg-slate-800 p-0.5 text-xs shrink-0">
                <button
                  type="button"
                  onClick={() => setTrendPeriod('month')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition ${
                    trendPeriod === 'month'
                      ? 'bg-white dark:bg-slate-900 shadow-sm text-slate-900 dark:text-white'
                      : 'text-slate-500'
                  }`}
                >
                  Tháng
                </button>
                <button
                  type="button"
                  onClick={() => setTrendPeriod('week')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition ${
                    trendPeriod === 'week'
                      ? 'bg-white dark:bg-slate-900 shadow-sm text-slate-900 dark:text-white'
                      : 'text-slate-500'
                  }`}
                >
                  Tuần
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Biến động tỷ lệ phàn nàn qua các kỳ
              </p>
              <select
                aria-label="Lọc xu hướng theo khía cạnh"
                value={trendAspect}
                onChange={(e) => setTrendAspect(e.target.value)}
                className="h-8 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 px-2.5"
              >
                <option value="">Tất cả khía cạnh</option>
                {Object.keys(ASPECT_META)
                  .filter((k) => k !== 'GENERAL')
                  .map((k) => (
                    <option key={k} value={k}>
                      {getAspectShortLabel(k)}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {loadingTrends ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-400">
              Đang tải dữ liệu xu hướng...
            </div>
          ) : trends.length === 0 ? (
            <EmptyState
              icon={Calendar}
              title="Chưa có dữ liệu theo kỳ"
              description="Không có đủ đánh giá có ngày tháng cho bộ lọc hiện tại."
            />
          ) : trends.length === 1 ? (
            /* Single Period Graceful Summary Card instead of a lonely dot chart */
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Kỳ ghi nhận duy nhất:{' '}
                  <strong className="text-slate-800 dark:text-white">{trends[0].period}</strong>
                </span>
                <Badge tone="neutral">{trends[0].total} ý kiến</Badge>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                  <div className="text-xs text-slate-500">Tỷ lệ phàn nàn</div>
                  <div className="text-xl font-bold text-rose-600 dark:text-rose-400 tabular-nums mt-0.5">
                    {trends[0].neg_pct}%
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                  <div className="text-xs text-slate-500">Tỷ lệ khen ngợi</div>
                  <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 tabular-nums mt-0.5">
                    {trends[0].pos_pct}%
                  </div>
                </div>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Bộ dữ liệu hiện tại tập trung trong kỳ <strong>{trends[0].period}</strong>. Đường xu hướng sẽ hiển thị khi có từ 2 kỳ thời gian trở lên (bạn có thể bấm sang chế độ xem theo <strong>Tuần</strong> hoặc chọn kịch bản <strong>real_shop</strong>).
              </p>
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <defs>
                    <linearGradient id="negGradNew" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#F43F5E" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#F43F5E" stopOpacity={0.0} />
                    </linearGradient>
                    <linearGradient id="posGradNew" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} strokeOpacity={0.6} />
                  <XAxis dataKey="period" tick={{ fontSize: 11, fill: axisColor }} />
                  <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11, fill: axisColor }} />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="rounded-xl bg-slate-900 text-white p-3 text-xs space-y-1 shadow-xl border border-slate-700">
                          <div className="font-bold">
                            Kỳ {d.period} ({d.total} ý kiến)
                          </div>
                          <div className="text-rose-400 font-semibold">
                            Phàn nàn: {d.neg_pct}% (Ước lượng: {d.wilson_ci_low}%–{d.wilson_ci_high}%)
                          </div>
                          <div className="text-emerald-400 font-semibold">
                            Khen ngợi: {d.pos_pct}%
                          </div>
                        </div>
                      );
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area
                    type="monotone"
                    dataKey="neg_pct"
                    name="Phàn nàn (%)"
                    stroke="#F43F5E"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#negGradNew)"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="pos_pct"
                    name="Khen ngợi (%)"
                    stroke="#10B981"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#posGradNew)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* Row 3: Shopee vs TikTok Shop Comparison (Clean 4-column table) */}
      <Card>
        <SectionHeader
          icon={Scale}
          title="So sánh trải nghiệm khách hàng: Shopee và TikTok Shop"
          subtitle="Đối chiếu tỷ lệ phàn nàn ở từng khía cạnh để biết sàn nào đang gặp vấn đề cần ưu tiên xử lý"
        />

        {platform_comparison.length === 0 ? (
          <EmptyState
            icon={Scale}
            title="Chưa đủ dữ liệu so sánh giữa 2 sàn"
            description="Cần tối thiểu 5 ý kiến ở mỗi sàn trong cùng một khía cạnh để so sánh chính xác."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 text-xs font-semibold">
                  <th className="py-2.5 px-3">Khía cạnh</th>
                  <th className="py-2.5 px-3">Shopee (Tỷ lệ chê)</th>
                  <th className="py-2.5 px-3">TikTok Shop (Tỷ lệ chê)</th>
                  <th className="py-2.5 px-3">Kết luận & Gợi ý</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
                {platform_comparison.map((row) => {
                  const statTooltip = `Độ lệch: ${row.gap_pct}% | Kiểm định thống kê z = ${row.z_score}, p = ${row.p_value}. Shopee 95% CI: [${row.shopee_ci_95?.[0]}%–${row.shopee_ci_95?.[1]}%], TikTok 95% CI: [${row.tiktok_ci_95?.[0]}%–${row.tiktok_ci_95?.[1]}%].`;

                  let summaryLabel = 'Hai sàn tương đương nhau';
                  let summaryTone = 'neutral';
                  if (row.significant) {
                    if (row.higher_platform === 'shopee') {
                      summaryLabel = `Shopee phàn nàn cao hơn rõ rệt (+${row.gap_pct}%)`;
                      summaryTone = 'danger';
                    } else if (row.higher_platform === 'tiktok') {
                      summaryLabel = `TikTok phàn nàn cao hơn rõ rệt (+${row.gap_pct}%)`;
                      summaryTone = 'danger';
                    }
                  } else if (row.gap_pct >= 10) {
                    summaryLabel =
                      row.higher_platform === 'shopee'
                        ? `Shopee cao hơn ${row.gap_pct}% (chưa đủ mẫu kết luận)`
                        : `TikTok cao hơn ${row.gap_pct}% (chưa đủ mẫu kết luận)`;
                    summaryTone = 'warning';
                  }

                  return (
                    <tr
                      key={row.aspect}
                      className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition"
                    >
                      <td className="py-3 px-3 font-semibold text-slate-900 dark:text-white">
                        {getAspectLabel(row.aspect)}
                      </td>
                      <td className="py-3 px-3 tabular-nums">
                        <span className="font-bold text-orange-600 dark:text-orange-400">
                          {row.shopee_neg_pct}%
                        </span>{' '}
                        <span className="text-xs text-slate-400">
                          ({row.shopee_total} ý kiến)
                        </span>
                      </td>
                      <td className="py-3 px-3 tabular-nums">
                        <span className="font-bold text-cyan-600 dark:text-cyan-400">
                          {row.tiktok_neg_pct}%
                        </span>{' '}
                        <span className="text-xs text-slate-400">
                          ({row.tiktok_total} ý kiến)
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <Badge tone={summaryTone}>{summaryLabel}</Badge>
                          <InfoTip text={statTooltip} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// CreBy: MenBoyBMN
