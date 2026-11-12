import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  FileSpreadsheet,
  FileText,
  Sun,
  Moon,
  Settings,
  RefreshCw,
  UploadCloud,
  MoreHorizontal,
} from 'lucide-react';
import { SCENARIO_OPTIONS } from '../constants/taxonomy';
import { api } from '../api/client';
import { Button, Modal } from './ui';

export default function Navbar({
  pageTitle,
  scenarioTag,
  onScenarioChange,
  darkMode,
  onToggleDark,
  onRefreshAll,
  onRunFullPipeline,
  isRunningPipeline,
  onOpenUploadModal,
  reviewer,
  onReviewerChange,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(
    () => localStorage.getItem('ecomreview_api_key') || ''
  );
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSaveSettings = (e) => {
    e.preventDefault();
    localStorage.setItem('ecomreview_api_key', apiKeyInput.trim());
    localStorage.setItem('ecomreview_reviewer', reviewer.trim() || 'chu_shop_aomua');
    setSettingsOpen(false);
    onRefreshAll();
  };

  const handleExport = (format) => {
    setMenuOpen(false);
    const url = api.getReportExportUrl(scenarioTag, format);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <>
      <header className="sticky top-0 z-20 h-14 bg-white/90 dark:bg-slate-900/90 backdrop-blur border-b border-slate-200/80 dark:border-slate-800 px-4 sm:px-6 flex items-center justify-between gap-3">
        {/* Left: Current Page Title */}
        <h1 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white truncate min-w-0">
          {pageTitle}
        </h1>

        {/* Right: Compact Scenario Selector + Primary Action + Overflow Menu */}
        <div className="flex items-center gap-2 shrink-0">
          <label className="sr-only" htmlFor="scenario-select">
            Chọn bộ dữ liệu
          </label>
          <select
            id="scenario-select"
            value={scenarioTag}
            onChange={(e) => onScenarioChange(e.target.value)}
            className="h-9 max-w-[210px] sm:max-w-[260px] truncate text-xs sm:text-sm font-medium rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-100 px-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
          >
            {SCENARIO_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <Button
            variant="secondary"
            size="md"
            onClick={onOpenUploadModal}
            className="hidden xl:inline-flex"
          >
            <UploadCloud className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Nạp đánh giá</span>
          </Button>

          <Button
            variant="primary"
            size="md"
            disabled={isRunningPipeline}
            onClick={onRunFullPipeline}
          >
            <Sparkles className={`w-4 h-4 ${isRunningPipeline ? 'animate-spin' : ''}`} />
            <span>{isRunningPipeline ? 'Đang phân tích...' : 'Chạy phân tích AI'}</span>
          </Button>

          {/* Overflow Menu "Thêm" */}
          <div className="relative" ref={menuRef}>
            <Button
              variant="secondary"
              size="md"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="Tác vụ khác"
              title="Xuất báo cáo, cài đặt và giao diện"
            >
              <MoreHorizontal className="w-4 h-4" />
              <span className="hidden sm:inline">Thêm</span>
            </Button>

            {menuOpen && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl py-1.5 z-40 text-xs font-medium animate-fade-in">
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onOpenUploadModal();
                  }}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden"
                >
                  <UploadCloud className="w-4 h-4 text-indigo-500" />
                  <span>Nạp đánh giá mới</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleExport('xlsx')}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                  <span>Tải báo cáo Excel (.xlsx)</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleExport('html')}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <FileText className="w-4 h-4 text-indigo-500" />
                  <span>Mở báo cáo in ấn (HTML)</span>
                </button>

                <div className="my-1 border-t border-slate-100 dark:border-slate-800" />

                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onRefreshAll();
                  }}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <RefreshCw className="w-4 h-4 text-slate-400" />
                  <span>Làm mới dữ liệu</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    onToggleDark();
                  }}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  {darkMode ? (
                    <>
                      <Sun className="w-4 h-4 text-amber-400" />
                      <span>Chuyển sang nền Sáng</span>
                    </>
                  ) : (
                    <>
                      <Moon className="w-4 h-4 text-slate-500" />
                      <span>Chuyển sang nền Tối</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setSettingsOpen(true);
                  }}
                  className="w-full px-3.5 py-2 flex items-center gap-2.5 text-left text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  <span>Cài đặt người duyệt ({reviewer})</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Reviewer & API Key Settings Modal */}
      <Modal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        title="Cài đặt người phê duyệt & kết nối"
        subtitle="Lưu tên người duyệt khi phê duyệt kế hoạch hành động"
        icon={Settings}
        maxWidth="max-w-md"
      >
        <form onSubmit={handleSaveSettings} className="space-y-4 text-sm">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Tên người duyệt kế hoạch
            </label>
            <input
              type="text"
              value={reviewer}
              onChange={(e) => onReviewerChange(e.target.value)}
              placeholder="chu_shop_aomua"
              className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
            <p className="text-xs text-slate-400 mt-1">
              Tên này sẽ được lưu kèm mỗi lần bạn bấm Duyệt, Sửa hoặc Từ chối hành động.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Mã bảo mật API (Tùy chọn)
            </label>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder="Để trống nếu chạy nội bộ"
              className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" size="sm" onClick={() => setSettingsOpen(false)}>
              Đóng
            </Button>
            <Button type="submit" variant="primary" size="sm">
              Lưu cài đặt
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

// CreBy: MenBoyBMN
