import React, { useState } from 'react';
import {
  BellRing,
  Lightbulb,
  Sparkles,
  FileSearch,
  CheckCircle2,
  AlertOctagon,
  Clock,
} from 'lucide-react';
import {
  INSIGHT_KIND_META,
  CONFIDENCE_LABELS,
  getAspectLabel,
} from '../constants/taxonomy';
import { api } from '../api/client';
import {
  Card,
  SectionHeader,
  Button,
  Badge,
  Segmented,
  EmptyState,
  Collapsible,
  InfoTip,
} from './ui';

export default function InsightsAlertsTab({
  scenarioTag,
  insights = [],
  alerts = [],
  onRefreshInsights,
  onOpenEvidence,
  showToast,
}) {
  const [selectedKind, setSelectedKind] = useState('ALL');
  const [runningAnalyze, setRunningAnalyze] = useState(false);
  const [asyncJobStatus, setAsyncJobStatus] = useState(null);

  const filteredInsights =
    selectedKind === 'ALL'
      ? insights
      : insights.filter((item) => item.kind === selectedKind);

  const kindCounts = insights.reduce((acc, item) => {
    acc[item.kind] = (acc[item.kind] || 0) + 1;
    return acc;
  }, {});

  const filterOptions = [
    { value: 'ALL', label: 'Tất cả', count: insights.length },
    ...Object.entries(INSIGHT_KIND_META).map(([key, meta]) => ({
      value: key,
      label: meta.shortLabel,
      count: kindCounts[key] || 0,
    })),
  ];

  const handleRunInsightEngine = async (asyncMode = false) => {
    try {
      setRunningAnalyze(true);
      const res = await api.runAnalysis({
        scenario_tag: scenarioTag,
        analyzer_method: 'a1_gemini_v2',
        min_n: 3,
        async_mode: asyncMode,
      });

      if (asyncMode && res.job_id) {
        setAsyncJobStatus({ jobId: res.job_id, status: 'running' });
        showToast(`Đang chạy phân tích ngầm (Mã tiến trình #${res.job_id})...`, 'info');
        const poll = setInterval(async () => {
          try {
            const job = await api.getJobStatus(res.job_id);
            setAsyncJobStatus({
              jobId: job.job_id,
              status: job.status,
              details: job.details,
            });
            if (job.status === 'completed' || job.status === 'failed') {
              clearInterval(poll);
              setRunningAnalyze(false);
              onRefreshInsights();
              showToast(
                job.status === 'completed'
                  ? 'Đã cập nhật danh sách phát hiện mới!'
                  : 'Tiến trình phân tích gặp sự cố.',
                job.status === 'completed' ? 'success' : 'error'
              );
            }
          } catch {
            clearInterval(poll);
            setRunningAnalyze(false);
          }
        }, 1200);
      } else {
        setRunningAnalyze(false);
        onRefreshInsights();
        showToast(
          `Đã cập nhật ${res.insights_generated || insights.length} phát hiện từ dữ liệu!`,
          'success'
        );
      }
    } catch (err) {
      setRunningAnalyze(false);
      showToast(err.message || 'Không thể chạy phân tích', 'error');
    }
  };

  return (
    <div className="space-y-5">
      {/* Section 1: Early Warning Banner */}
      <Card>
        <SectionHeader
          icon={BellRing}
          title="Cảnh báo phàn nàn tăng đột biến"
          subtitle="Phát hiện các khía cạnh có tỷ lệ chê trong kỳ gần nhất tăng mạnh bất thường so với trung bình các kỳ trước"
          actions={
            <Badge tone={alerts.length > 0 ? 'danger' : 'success'}>
              {alerts.length > 0 ? `${alerts.length} cảnh báo cần chú ý` : 'Trạng thái ổn định'}
            </Badge>
          }
        />

        {alerts.length === 0 ? (
          <div className="p-3.5 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/50 flex items-center gap-2.5 text-sm text-emerald-800 dark:text-emerald-300">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>
              Tất cả các khía cạnh sản phẩm đang ổn định, không có đợt tăng vọt phàn nàn bất thường nào trong kỳ gần nhất.
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {alerts.map((al, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl bg-rose-50/60 dark:bg-rose-950/25 border border-rose-200/80 dark:border-rose-800/60 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <AlertOctagon className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
                    <span className="text-sm font-bold text-slate-900 dark:text-white truncate">
                      {getAspectLabel(al.aspect)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge tone="danger">Tăng +{al.delta_pp}%</Badge>
                    <InfoTip
                      text={`Kỳ ${al.period}: ${al.latest_neg_pct}% chê (${al.latest_n} mẫu) so với nền trước đó ${al.baseline_neg_pct}% (${al.baseline_n} mẫu). Kiểm định z = ${al.z_score}, p = ${al.p_value}.`}
                    />
                  </div>
                </div>
                <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                  Tỷ lệ phàn nàn tăng từ <strong>{al.baseline_neg_pct}%</strong> lên{' '}
                  <strong className="text-rose-600 dark:text-rose-400">{al.latest_neg_pct}%</strong>{' '}
                  trong kỳ <strong>{al.period}</strong>. Shop nên kiểm tra lại chất lượng lô hàng gần nhất.
                </p>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Section 2: Insights Explorer */}
      <Card className="space-y-4">
        <SectionHeader
          icon={Lightbulb}
          title="Các phát hiện quan trọng từ đánh giá khách hàng"
          subtitle="Mọi con số thống kê dưới đây đều được đối chiếu tự động từ cơ sở dữ liệu và gắn kèm đánh giá thật làm bằng chứng"
          actions={
            <>
              <Button
                variant="primary"
                size="sm"
                disabled={runningAnalyze}
                onClick={() => handleRunInsightEngine(false)}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{runningAnalyze ? 'Đang cập nhật...' : 'Cập nhật phát hiện'}</span>
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={runningAnalyze}
                onClick={() => handleRunInsightEngine(true)}
                title="Chạy ngầm không chặn giao diện"
              >
                <Clock className="w-3.5 h-3.5 text-indigo-500" />
                <span>Chạy ngầm</span>
              </Button>
            </>
          }
        />

        {asyncJobStatus && (
          <div className="p-3 rounded-xl bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-indigo-600" />
              <span>
                Tiến trình chạy ngầm <strong>#{asyncJobStatus.jobId}</strong>:{' '}
                <strong className="text-indigo-600 dark:text-indigo-400">
                  {asyncJobStatus.status === 'completed' ? 'Hoàn tất' : 'Đang xử lý...'}
                </strong>
              </span>
            </div>
            <button
              type="button"
              onClick={() => setAsyncJobStatus(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              Đóng
            </button>
          </div>
        )}

        {/* Segmented Filter */}
        <Segmented
          options={filterOptions}
          value={selectedKind}
          onChange={setSelectedKind}
        />

        {/* Single-Column Clean Insight Cards */}
        {filteredInsights.length === 0 ? (
          <EmptyState
            icon={Lightbulb}
            title="Chưa có phát hiện nào trong mục này"
            description="Hãy chọn mục Tất cả hoặc bấm nút Cập nhật phát hiện ở góc trên."
          />
        ) : (
          <div className="space-y-3">
            {filteredInsights.map((ins) => {
              const meta = INSIGHT_KIND_META[ins.kind] || {
                label: ins.kind,
                tone: 'neutral',
                accentBorder: 'border-l-slate-400',
              };
              const evIds = ins.evidence_ids || [];
              const confLabel = CONFIDENCE_LABELS[ins.confidence] || ins.confidence;

              return (
                <div
                  key={ins.insight_id}
                  className={`p-4 sm:p-5 rounded-2xl border border-slate-200/90 dark:border-slate-800 border-l-4 ${meta.accentBorder} bg-white dark:bg-slate-900 space-y-3`}
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      <span className="text-sm font-bold text-slate-900 dark:text-white">
                        {getAspectLabel(ins.aspect)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge tone="neutral">{confLabel}</Badge>
                      {evIds.length > 0 && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            onOpenEvidence(evIds, `${meta.label} — ${getAspectLabel(ins.aspect)}`)
                          }
                        >
                          <FileSearch className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                          <span>Xem {evIds.length} đánh giá gốc</span>
                        </Button>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-slate-800 dark:text-slate-100 leading-relaxed">
                    {ins.statement}
                  </p>

                  {/* Collapsible Technical Numbers & Review IDs */}
                  {(evIds.length > 0 || (ins.numbers && Object.keys(ins.numbers).length > 0)) && (
                    <Collapsible title="Xem mã đánh giá bằng chứng & chi tiết số liệu">
                      <div className="space-y-2.5">
                        {evIds.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-slate-500">Mã đánh giá gốc:</span>
                            {evIds.map((rid) => (
                              <button
                                key={rid}
                                type="button"
                                onClick={() =>
                                  onOpenEvidence([rid], `${meta.label} — ${getAspectLabel(ins.aspect)}`)
                                }
                                className="px-2 py-0.5 rounded-md font-mono text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/70 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-800 transition"
                              >
                                #{rid}
                              </button>
                            ))}
                          </div>
                        )}

                        {ins.numbers && Object.keys(ins.numbers).length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-slate-500">Chỉ số thống kê:</span>
                            {Object.entries(ins.numbers).map(([k, v]) => (
                              <span
                                key={k}
                                className="px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-mono text-xs text-slate-600 dark:text-slate-300"
                              >
                                {k}: <strong>{String(v)}</strong>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </Collapsible>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

// CreBy: MenBoyBMN
