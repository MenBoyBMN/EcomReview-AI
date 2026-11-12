import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { api } from './api/client';
import Sidebar, { NAV_ITEMS } from './components/Sidebar';
import Navbar from './components/Navbar';
import OverviewTab from './components/OverviewTab';
import InsightsAlertsTab from './components/InsightsAlertsTab';
import ActionsTab from './components/ActionsTab';
import ReviewsCskhTab from './components/ReviewsCskhTab';
import EvidenceModal from './components/EvidenceModal';
import UploadModal from './components/UploadModal';

const VALID_TAB_IDS = new Set(NAV_ITEMS.map((item) => item.id));

function getInitialTabFromHash() {
  const hash = (window.location.hash || '').replace(/^#/, '').trim();
  return VALID_TAB_IDS.has(hash) ? hash : 'overview';
}

function getInitialScenarioFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('scenario') || 'real_shop';
}

export default function App() {
  const [activeTab, setActiveTab] = useState(getInitialTabFromHash);
  const [scenarioTag, setScenarioTag] = useState(getInitialScenarioFromUrl);
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('ecomreview_theme') === 'dark';
  });
  const [reviewer, setReviewer] = useState(() => {
    return localStorage.getItem('ecomreview_reviewer') || 'chu_shop_aomua';
  });

  // Pre-selected aspect when navigating from Overview -> Reviews
  const [selectedReviewAspect, setSelectedReviewAspect] = useState('');

  // Core data states
  const [health, setHealth] = useState(null);
  const [overview, setOverview] = useState(null);
  const [insights, setInsights] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [actions, setActions] = useState([]);
  const [loadingOverview, setLoadingOverview] = useState(true);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Modals & Toasts
  const [evidenceModal, setEvidenceModal] = useState({
    isOpen: false,
    reviewIds: [],
    contextTitle: '',
  });
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [toast, setToast] = useState(null);

  const handleSelectTab = useCallback((tabId) => {
    setActiveTab(tabId);
    window.history.replaceState(null, '', `#${tabId}`);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setActiveTab(getInitialTabFromHash());
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add('dark');
      localStorage.setItem('ecomreview_theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('ecomreview_theme', 'light');
    }
  }, [darkMode]);

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast((prev) => (prev?.message === message ? null : prev));
    }, 4000);
  }, []);

  const loadScenarioData = useCallback(async () => {
    setLoadingOverview(true);
    try {
      const [healthRes, overviewRes, insightsRes, alertsRes, actionsRes] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getOverviewStats(scenarioTag, 3),
        api.getInsights(scenarioTag),
        api.getAlerts(scenarioTag, 'month', 3, 8.0).catch(() => ({ alerts: [] })),
        api.getActions(scenarioTag),
      ]);

      if (healthRes) setHealth(healthRes);
      setOverview(overviewRes);
      setInsights(insightsRes.insights || []);
      setAlerts(alertsRes.alerts || []);
      setActions(actionsRes.actions || []);
    } catch (err) {
      showToast(
        err.message ||
          'Không thể kết nối tới máy chủ Backend (Hãy đảm bảo uvicorn đang chạy ở cổng 8000)',
        'error'
      );
    } finally {
      setLoadingOverview(false);
    }
  }, [scenarioTag, showToast]);

  useEffect(() => {
    loadScenarioData();
  }, [loadScenarioData]);

  const handleRunFullPipeline = async () => {
    try {
      setIsRunningPipeline(true);
      showToast(`Đang phân tích dữ liệu và lập kế hoạch cho kịch bản ${scenarioTag}...`, 'info');
      await api.runAnalysis({
        scenario_tag: scenarioTag,
        analyzer_method: 'a1_gemini_v2',
        min_n: 3,
        async_mode: false,
      });
      const trace = await api.generateActions(scenarioTag, 3, 6);
      await loadScenarioData();
      setRefreshTrigger((v) => v + 1);
      showToast(
        `Hoàn tất! Đã tổng hợp ${trace.insights_count} phát hiện và ${trace.actions_count} đề xuất hành động.`,
        'success'
      );
    } catch (err) {
      showToast(err.message || 'Không thể chạy phân tích AI', 'error');
    } finally {
      setIsRunningPipeline(false);
    }
  };

  const handleOpenEvidence = (reviewIds, contextTitle = '') => {
    setEvidenceModal({
      isOpen: true,
      reviewIds,
      contextTitle,
    });
  };

  const handleNavigateReviewsWithAspect = (aspectCode) => {
    setSelectedReviewAspect(aspectCode);
    handleSelectTab('reviews');
  };

  const pendingActionsCount = actions.filter(
    (a) => (a.status || 'PENDING').toUpperCase() === 'PENDING'
  ).length;

  const currentNavItem = NAV_ITEMS.find((item) => item.id === activeTab) || NAV_ITEMS[0];

  return (
    <div className="min-h-screen flex bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      {/* Left Navigation Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        insightsCount={insights.length}
        pendingActionsCount={pendingActionsCount}
        actionsCount={actions.length}
        health={health}
      />

      {/* Right Main Workspace */}
      <div className="flex-1 min-w-0 flex flex-col">
        <Navbar
          pageTitle={currentNavItem.pageTitle}
          scenarioTag={scenarioTag}
          onScenarioChange={setScenarioTag}
          darkMode={darkMode}
          onToggleDark={() => setDarkMode((d) => !d)}
          onRefreshAll={() => {
            loadScenarioData();
            setRefreshTrigger((v) => v + 1);
          }}
          onRunFullPipeline={handleRunFullPipeline}
          isRunningPipeline={isRunningPipeline}
          onOpenUploadModal={() => setUploadModalOpen(true)}
          reviewer={reviewer}
          onReviewerChange={(val) => {
            setReviewer(val);
            localStorage.setItem('ecomreview_reviewer', val);
          }}
        />

        <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-5">
          {activeTab === 'overview' && (
            <OverviewTab
              overview={overview}
              scenarioTag={scenarioTag}
              loadingOverview={loadingOverview}
              darkMode={darkMode}
              onNavigateReviewsWithAspect={handleNavigateReviewsWithAspect}
            />
          )}

          {activeTab === 'insights' && (
            <InsightsAlertsTab
              scenarioTag={scenarioTag}
              insights={insights}
              alerts={alerts}
              onRefreshInsights={loadScenarioData}
              onOpenEvidence={handleOpenEvidence}
              showToast={showToast}
            />
          )}

          {activeTab === 'actions' && (
            <ActionsTab
              scenarioTag={scenarioTag}
              actions={actions}
              onRefreshActions={loadScenarioData}
              onOpenEvidence={handleOpenEvidence}
              showToast={showToast}
            />
          )}

          {activeTab === 'reviews' && (
            <ReviewsCskhTab
              scenarioTag={scenarioTag}
              initialAspect={selectedReviewAspect}
              onClearInitialAspect={() => setSelectedReviewAspect('')}
              onOpenUploadModal={() => setUploadModalOpen(true)}
              showToast={showToast}
              refreshTrigger={refreshTrigger}
            />
          )}
        </main>

        <footer className="border-t border-slate-200/70 dark:border-slate-800/80 py-3.5 px-4 sm:px-6 text-xs text-slate-400">
          <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>
              <strong>EcomReview AI</strong> — Hệ thống phân tích phản hồi tiếng Việt & lập kế hoạch Marketing cho doanh nghiệp nhỏ
            </span>
            <span>Dữ liệu xác thực 100% từ CSDL • Kiểm định an toàn tự động</span>
          </div>
        </footer>
      </div>

      {/* Ground-Truth Evidence Drill-Down Modal */}
      <EvidenceModal
        isOpen={evidenceModal.isOpen}
        onClose={() => setEvidenceModal((prev) => ({ ...prev, isOpen: false }))}
        scenarioTag={scenarioTag}
        reviewIds={evidenceModal.reviewIds}
        contextTitle={evidenceModal.contextTitle}
      />

      {/* Upload New Review Modal */}
      <UploadModal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        scenarioTag={scenarioTag}
        onSuccess={() => {
          loadScenarioData();
          setRefreshTrigger((v) => v + 1);
        }}
        showToast={showToast}
      />

      {/* Calm Slide-Up Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 max-w-md animate-slide-up">
          <div
            className={`px-4 py-3 rounded-2xl shadow-xl border flex items-center justify-between gap-3 text-xs font-semibold ${
              toast.type === 'error'
                ? 'bg-rose-600 text-white border-rose-500'
                : toast.type === 'success'
                ? 'bg-emerald-600 text-white border-emerald-500'
                : 'bg-slate-900 text-white dark:bg-slate-800 dark:text-slate-100 border-slate-700'
            }`}
          >
            <div className="flex items-center gap-2.5">
              {toast.type === 'error' ? (
                <AlertCircle className="w-4 h-4 shrink-0" />
              ) : toast.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 shrink-0" />
              ) : (
                <Info className="w-4 h-4 shrink-0" />
              )}
              <span>{toast.message}</span>
            </div>
            <button
              type="button"
              onClick={() => setToast(null)}
              className="p-0.5 rounded hover:bg-white/20 shrink-0"
              aria-label="Đóng thông báo"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// CreBy: MenBoyBMN
