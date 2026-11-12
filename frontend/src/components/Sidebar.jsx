import React from 'react';
import {
  CloudRain,
  LayoutDashboard,
  Lightbulb,
  Megaphone,
  MessageSquareText,
} from 'lucide-react';

export const NAV_ITEMS = [
  {
    id: 'overview',
    label: 'Tổng quan',
    pageTitle: 'Tổng quan gian hàng',
    icon: LayoutDashboard,
  },
  {
    id: 'insights',
    label: 'Phát hiện chính',
    pageTitle: 'Phát hiện & Cảnh báo sớm',
    icon: Lightbulb,
  },
  {
    id: 'actions',
    label: 'Kế hoạch hành động',
    pageTitle: 'Kế hoạch hành động',
    icon: Megaphone,
  },
  {
    id: 'reviews',
    label: 'Đánh giá & CSKH',
    pageTitle: 'Kho đánh giá & Trợ lý CSKH',
    icon: MessageSquareText,
  },
];

export default function Sidebar({
  activeTab,
  onSelectTab,
  insightsCount = 0,
  pendingActionsCount = 0,
  actionsCount = 0,
  health,
}) {
  const isHealthy = health?.status === 'healthy';

  return (
    <aside className="w-16 xl:w-64 shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200/90 dark:border-slate-800 flex flex-col justify-between sticky top-0 h-screen z-30 select-none">
      {/* Top: Brand + Nav */}
      <div>
        {/* Brand Header */}
        <div className="h-14 px-3 xl:px-5 border-b border-slate-200/80 dark:border-slate-800 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm shadow-indigo-500/20 shrink-0 mx-auto xl:mx-0">
            <CloudRain className="w-5 h-5" />
          </div>
          <div className="hidden xl:block min-w-0">
            <div className="text-sm font-bold text-slate-900 dark:text-white leading-tight">
              EcomReview AI
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Phân tích & CSKH TMĐT
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="p-2 xl:p-3 space-y-1" aria-label="Điều hướng chính">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            const badgeVal =
              item.id === 'insights'
                ? insightsCount
                : item.id === 'actions'
                ? pendingActionsCount || actionsCount
                : 0;
            const isPendingBadge = item.id === 'actions' && pendingActionsCount > 0;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                title={item.label}
                className={`w-full flex items-center justify-center xl:justify-between gap-2 px-2.5 xl:px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  active
                    ? 'bg-indigo-50 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300 font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/80 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      active
                        ? 'text-indigo-600 dark:text-indigo-400'
                        : 'text-slate-400 dark:text-slate-500'
                    }`}
                  />
                  <span className="hidden xl:inline whitespace-nowrap">{item.label}</span>
                </div>

                {badgeVal > 0 && (
                  <span
                    className={`hidden xl:inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold tabular-nums shrink-0 ${
                      isPendingBadge
                        ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                        : active
                        ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/80 dark:text-indigo-200'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                    }`}
                  >
                    {badgeVal}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom: Compact Connection Status */}
      <div className="p-2 xl:p-3 border-t border-slate-200/80 dark:border-slate-800">
        <div
          title={
            isHealthy
              ? `Máy chủ sẵn sàng • Cơ sở dữ liệu: ${health.database_backend?.toUpperCase()} • Tổng ${health.total_reviews_in_db} đánh giá`
              : 'Chưa kết nối được với máy chủ Backend (cổng 8000)'
          }
          className="flex items-center justify-center xl:justify-start gap-2.5 px-2.5 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-600 dark:text-slate-300"
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              isHealthy ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
          />
          <div className="hidden xl:block min-w-0 truncate">
            <span className="font-semibold">
              {isHealthy ? 'Hệ thống sẵn sàng' : 'Mất kết nối API'}
            </span>
            {isHealthy && (
              <span className="text-slate-400 dark:text-slate-500 ml-1">
                ({health.total_reviews_in_db} mẫu)
              </span>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

// CreBy: MenBoyBMN
