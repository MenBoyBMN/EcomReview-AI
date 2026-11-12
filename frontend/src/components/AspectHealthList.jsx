import React from 'react';
import { ChevronRight, BarChart2 } from 'lucide-react';
import { ASPECT_META, CONFIDENCE_LABELS, getAspectLabel } from '../constants/taxonomy';
import { EmptyState, InfoTip } from './ui';

export default function AspectHealthList({ aspectStats = [], onSelectAspect }) {
  if (!aspectStats || aspectStats.length === 0) {
    return (
      <EmptyState
        icon={BarChart2}
        title="Chưa có dữ liệu phân tích theo khía cạnh"
        description="Hãy bấm nút Chạy phân tích AI ở góc trên để trích xuất ý kiến khách hàng."
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* Legend */}
      <div className="flex items-center justify-between flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400 pb-1">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500" />
            <span>Phàn nàn (Tiêu cực)</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-slate-300 dark:bg-slate-600" />
            <span>Trung lập</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />
            <span>Khen ngợi (Tích cực)</span>
          </span>
        </div>
        <span>Bấm vào khía cạnh để xem đánh giá chi tiết</span>
      </div>

      {/* Aspect Rows */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800/80">
        {aspectStats.map((item) => {
          const negPct = Number(item.neg_pct || 0);
          const posPct = Number(item.pos_pct || 0);
          const neuPct = Math.max(0, Number((100 - negPct - posPct).toFixed(1)));
          const meta = ASPECT_META[item.aspect] || {};
          const confLabel = CONFIDENCE_LABELS[item.confidence] || item.confidence;

          const tooltipText = `Tổng ${item.total} ý kiến (${confLabel}). Phàn nàn: ${item.neg_count} bài (Khoảng tin cậy 95%: ${item.wilson_ci_low}% – ${item.wilson_ci_high}%). Khen ngợi: ${item.pos_count} bài (${item.pos_wilson_ci_low}% – ${item.pos_wilson_ci_high}%).`;

          return (
            <div
              key={item.aspect}
              onClick={() => onSelectAspect && onSelectAspect(item.aspect)}
              role={onSelectAspect ? 'button' : undefined}
              tabIndex={onSelectAspect ? 0 : undefined}
              onKeyDown={(e) => {
                if (onSelectAspect && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onSelectAspect(item.aspect);
                }
              }}
              className="py-3 px-2 -mx-2 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/50 transition group cursor-pointer"
            >
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-semibold text-slate-900 dark:text-white truncate">
                    {getAspectLabel(item.aspect)}
                  </span>
                  <span className="text-xs text-slate-400 tabular-nums shrink-0">
                    ({item.total} ý kiến)
                  </span>
                  <span onClick={(e) => e.stopPropagation()}>
                    <InfoTip text={tooltipText} />
                  </span>
                </div>

                <div className="flex items-center gap-3 shrink-0 text-xs tabular-nums">
                  <span className="font-semibold text-rose-600 dark:text-rose-400">
                    {negPct}% chê
                  </span>
                  <span className="text-slate-300 dark:text-slate-700">•</span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                    {posPct}% khen
                  </span>
                  {onSelectAspect && (
                    <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-indigo-500 transition" />
                  )}
                </div>
              </div>

              {/* Segmented Horizontal Health Bar */}
              <div className="h-2.5 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex">
                {negPct > 0 && (
                  <div
                    style={{ width: `${negPct}%` }}
                    className="bg-rose-500 h-full transition-all duration-300"
                    title={`Phàn nàn: ${negPct}% (${item.neg_count} ý kiến)`}
                  />
                )}
                {neuPct > 0 && (
                  <div
                    style={{ width: `${neuPct}%` }}
                    className="bg-slate-300 dark:bg-slate-600 h-full transition-all duration-300"
                    title={`Trung lập: ${neuPct}% (${item.neu_count} ý kiến)`}
                  />
                )}
                {posPct > 0 && (
                  <div
                    style={{ width: `${posPct}%` }}
                    className="bg-emerald-500 h-full transition-all duration-300"
                    title={`Khen ngợi: ${posPct}% (${item.pos_count} ý kiến)`}
                  />
                )}
              </div>

              {meta.desc && (
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 truncate">
                  {meta.desc}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// CreBy: MenBoyBMN

