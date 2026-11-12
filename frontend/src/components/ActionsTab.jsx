import React, { useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Edit3,
  XCircle,
  BarChart3,
  FileSearch,
  Clock,
  Target,
  Zap,
  Megaphone,
  Wrench,
  ChevronDown,
} from 'lucide-react';
import { api } from '../api/client';
import {
  ACTION_TYPE_META,
  STATUS_META,
  EFFORT_LABELS,
  IMPACT_LABELS,
  CRITIC_RULES_SUMMARY,
} from '../constants/taxonomy';
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
import DecisionModal from './DecisionModal';

export default function ActionsTab({
  scenarioTag,
  actions = [],
  onRefreshActions,
  onOpenEvidence,
  showToast,
}) {
  const [categoryFilter, setCategoryFilter] = useState('ALL'); // ALL, MARKETING, OPS
  const [statusFilter, setStatusFilter] = useState('ALL'); // ALL, PENDING, APPROVED, EDITED, REJECTED
  const [generating, setGenerating] = useState(false);
  const [lastTrace, setLastTrace] = useState(null);
  const [expandedIds, setExpandedIds] = useState(() => new Set());

  // Decision Modal state
  const [decisionModal, setDecisionModal] = useState({
    isOpen: false,
    actionItem: null,
    mode: 'EDITED',
  });
  const [submittingDecision, setSubmittingDecision] = useState(false);

  // Impact measurement state per action
  const [impactMap, setImpactMap] = useState({});
  const [loadingImpactId, setLoadingImpactId] = useState(null);
  const [customSinceDate, setCustomSinceDate] = useState('2026-02-01');

  const toggleExpand = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const mktCount = actions.filter((a) => a.is_marketing).length;
  const opsCount = actions.filter((a) => !a.is_marketing).length;

  const statusCounts = actions.reduce(
    (acc, a) => {
      const st = (a.status || 'PENDING').toUpperCase();
      acc[st] = (acc[st] || 0) + 1;
      return acc;
    },
    { PENDING: 0, APPROVED: 0, EDITED: 0, REJECTED: 0 }
  );

  const filteredActions = actions.filter((act) => {
    if (categoryFilter === 'MARKETING' && !act.is_marketing) return false;
    if (categoryFilter === 'OPS' && act.is_marketing) return false;
    if (statusFilter !== 'ALL' && (act.status || 'PENDING').toUpperCase() !== statusFilter) {
      return false;
    }
    return true;
  });

  const handleGenerateStateGraph = async () => {
    try {
      setGenerating(true);
      const trace = await api.generateActions(scenarioTag, 3, 6);
      setLastTrace(trace);
      await onRefreshActions();
      showToast(
        `Đã lập xong ${trace.actions_count} đề xuất hành động mới (Đạt chuẩn kiểm định ${trace.final_critic_score}/5.0)!`,
        'success'
      );
    } catch (err) {
      showToast(err.message || 'Không thể tạo kế hoạch mới', 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleQuickApprove = async (actionId) => {
    try {
      setSubmittingDecision(true);
      const res = await api.submitActionDecision(actionId, {
        decision: 'APPROVED',
        note: 'Phê duyệt triển khai từ bảng điều hành',
        edited_content: '',
        reason_category: 'ready_to_execute',
      });
      await onRefreshActions();
      showToast(`Đã duyệt hành động #${actionId} (Người duyệt: ${res.decided_by})!`, 'success');
    } catch (err) {
      showToast(err.message || 'Không thể lưu quyết định duyệt', 'error');
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleSubmitModalDecision = async ({
    actionId,
    decision,
    edited_content,
    reason_category,
    note,
  }) => {
    try {
      setSubmittingDecision(true);
      await api.submitActionDecision(actionId, {
        decision,
        edited_content,
        reason_category,
        note,
      });
      setDecisionModal({ isOpen: false, actionItem: null, mode: 'EDITED' });
      await onRefreshActions();
      showToast(
        decision === 'EDITED'
          ? `Đã lưu nội dung chỉnh sửa & duyệt hành động #${actionId}!`
          : `Đã từ chối đề xuất #${actionId}.`,
        'success'
      );
    } catch (err) {
      showToast(err.message || 'Không thể lưu quyết định', 'error');
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleMeasureImpact = async (actionId) => {
    try {
      setLoadingImpactId(actionId);
      const res = await api.getActionImpact(actionId, 45, customSinceDate, 2);
      setImpactMap((prev) => ({ ...prev, [actionId]: res }));
    } catch (err) {
      showToast(err.message || 'Không thể đo hiệu quả', 'error');
    } finally {
      setLoadingImpactId(null);
    }
  };

  const categoryOptions = [
    { value: 'ALL', label: 'Tất cả hạng mục', count: actions.length },
    { value: 'MARKETING', label: 'Marketing & Gian hàng', icon: Megaphone, count: mktCount },
    { value: 'OPS', label: 'Sản phẩm & Kho vận', icon: Wrench, count: opsCount },
  ];

  return (
    <div className="space-y-5">
      {/* Row 1: Header + Status Filter Tiles */}
      <Card className="space-y-4">
        <SectionHeader
          icon={Megaphone}
          title="Đề xuất hành động cụ thể cho Shop"
          subtitle="Mỗi việc cần làm đều được sắp xếp theo mức độ ưu tiên, có hạn hoàn thành và gắn kèm đánh giá thực tế của khách hàng"
          actions={
            <Button
              variant="primary"
              size="md"
              disabled={generating}
              onClick={handleGenerateStateGraph}
            >
              <Sparkles className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
              <span>{generating ? 'Đang lập kế hoạch...' : 'Tạo kế hoạch mới'}</span>
            </Button>
          }
        />

        {/* 4 Status Filter Pills */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { key: 'ALL', label: 'Tổng số đề xuất', count: actions.length, color: 'text-slate-900 dark:text-white' },
            { key: 'PENDING', label: 'Đang chờ duyệt', count: statusCounts.PENDING, color: 'text-amber-600 dark:text-amber-400' },
            {
              key: 'APPROVED',
              label: 'Đã phê duyệt',
              count: statusCounts.APPROVED + statusCounts.EDITED,
              color: 'text-emerald-600 dark:text-emerald-400',
            },
            { key: 'REJECTED', label: 'Đã từ chối', count: statusCounts.REJECTED, color: 'text-rose-600 dark:text-rose-400' },
          ].map((tile) => {
            const active = statusFilter === tile.key;
            return (
              <button
                key={tile.key}
                type="button"
                onClick={() => setStatusFilter(tile.key)}
                className={`p-3.5 rounded-xl border text-left transition ${
                  active
                    ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 ring-1 ring-indigo-500'
                    : 'border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 hover:bg-slate-100/70 dark:hover:bg-slate-800'
                }`}
              >
                <div className="text-xs text-slate-500 dark:text-slate-400">{tile.label}</div>
                <div className={`text-2xl font-bold tabular-nums mt-0.5 ${tile.color}`}>
                  {tile.count}
                </div>
              </button>
            );
          })}
        </div>

        {/* Category Filter Bar */}
        <div className="flex items-center justify-between flex-wrap gap-3 pt-1">
          <Segmented
            options={categoryOptions}
            value={categoryFilter}
            onChange={setCategoryFilter}
          />

          {statusFilter !== 'ALL' && (
            <Button variant="ghost" size="sm" onClick={() => setStatusFilter('ALL')}>
              Xóa bộ lọc trạng thái ({STATUS_META[statusFilter]?.label || statusFilter})
            </Button>
          )}
        </div>
      </Card>

      {/* Row 2: Action Proposals List */}
      {filteredActions.length === 0 ? (
        <Card>
          <EmptyState
            icon={Megaphone}
            title="Không có đề xuất hành động nào khớp bộ lọc"
            description="Bạn có thể chuyển sang xem Tất cả hạng mục hoặc bấm nút Tạo kế hoạch mới."
          />
        </Card>
      ) : (
        <div className="space-y-3.5">
          {filteredActions.map((act) => {
            const typeMeta = ACTION_TYPE_META[act.action_type] || {
              label: act.action_type,
              category: act.is_marketing ? 'Marketing' : 'Vận hành & Sản phẩm',
              tone: 'neutral',
            };
            const statusUpper = (act.status || 'PENDING').toUpperCase();
            const statusInfo = STATUS_META[statusUpper] || STATUS_META.PENDING;
            const evIds = act.evidence_review_ids || [];
            const isExpanded = expandedIds.has(act.id);
            const impactData = impactMap[act.id];

            const priorityTier =
              act.priority_score >= 2.5
                ? { label: 'Ưu tiên cao', tone: 'danger' }
                : act.priority_score >= 1.5
                ? { label: 'Ưu tiên vừa', tone: 'warning' }
                : { label: 'Ưu tiên thấp', tone: 'neutral' };

            return (
              <Card key={act.id} className="space-y-3.5">
                {/* Top Summary Line */}
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone={act.is_marketing ? 'info' : 'warning'}>
                        {act.is_marketing ? 'Marketing' : 'Sản phẩm & Kho'}
                      </Badge>
                      <Badge tone={typeMeta.tone}>{typeMeta.label}</Badge>
                      <Badge tone={priorityTier.tone}>{priorityTier.label}</Badge>
                      <InfoTip
                        text={`Điểm ưu tiên: ${act.priority_score} | Mức độ tác động: ${
                          IMPACT_LABELS[act.impact] || act.impact
                        } | Công sức: ${EFFORT_LABELS[act.effort] || act.effort}.`}
                      />
                    </div>

                    <h3 className="text-base font-bold text-slate-900 dark:text-white leading-snug">
                      {act.title}
                    </h3>
                  </div>

                  {/* Status Badge */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
                  </div>
                </div>

                {/* Concise Preview (Always visible) */}
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                  {act.what_to_do}
                </p>

                <div className="flex items-center gap-4 flex-wrap text-xs text-slate-500 dark:text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                    <span>{act.how_and_when}</span>
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    <span>Mục tiêu: {act.success_metric}</span>
                  </span>
                </div>

                {/* Action Bar: Details toggle + Evidence + Approve / Edit / Reject */}
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleExpand(act.id)}
                    >
                      <ChevronDown
                        className={`w-4 h-4 transition-transform ${
                          isExpanded ? 'rotate-180' : ''
                        }`}
                      />
                      <span>{isExpanded ? 'Thu gọn chi tiết' : 'Xem chi tiết & đo hiệu quả'}</span>
                    </Button>

                    {evIds.length > 0 && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => onOpenEvidence(evIds, act.title)}
                      >
                        <FileSearch className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                        <span>Xem {evIds.length} đánh giá gốc</span>
                      </Button>
                    )}
                  </div>

                  {/* Approval Gate Buttons */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      variant="success"
                      size="sm"
                      disabled={submittingDecision}
                      onClick={() => handleQuickApprove(act.id)}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Duyệt</span>
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setDecisionModal({ isOpen: true, actionItem: act, mode: 'EDITED' })
                      }
                    >
                      <Edit3 className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      <span>Sửa</span>
                    </Button>

                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() =>
                        setDecisionModal({ isOpen: true, actionItem: act, mode: 'REJECTED' })
                      }
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Từ chối</span>
                    </Button>
                  </div>
                </div>

                {/* Expanded 4-Pillar Detail + Pre/Post Impact Measurement */}
                {isExpanded && (
                  <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-4 animate-fade-in">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 space-y-1">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                          <Zap className="w-3.5 h-3.5" /> 1. Các bước thực hiện cụ thể
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                          {act.what_to_do}
                        </p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 space-y-1">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
                          <BarChart3 className="w-3.5 h-3.5" /> 2. Vì sao cần làm (Căn cứ số liệu)
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                          {act.why_rationale}
                        </p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 space-y-1">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                          <Clock className="w-3.5 h-3.5" /> 3. Kênh & thời hạn hoàn thành
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                          {act.how_and_when}
                        </p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 space-y-1">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                          <Target className="w-3.5 h-3.5" /> 4. Tiêu chí đo lường thành công
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                          {act.success_metric}
                        </p>
                      </div>
                    </div>

                    {/* Evidence Chips + Impact Measurement Trigger */}
                    <div className="p-3.5 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3 text-xs">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-slate-500">Mã đánh giá gốc:</span>
                        {evIds.map((rid) => (
                          <button
                            key={rid}
                            type="button"
                            onClick={() => onOpenEvidence([rid], act.title)}
                            className="px-2 py-0.5 rounded font-mono font-semibold bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 border border-slate-200 dark:border-slate-700 hover:border-indigo-400 transition"
                          >
                            #{rid}
                          </button>
                        ))}
                        {act.critic_passed && (
                          <Badge tone="success" className="ml-1">
                            <ShieldCheck className="w-3 h-3" /> Đạt 7/7 quy tắc an toàn
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-2 flex-wrap">
                        <label className="text-slate-500">Mốc ngày áp dụng:</label>
                        <input
                          type="date"
                          value={customSinceDate}
                          onChange={(e) => setCustomSinceDate(e.target.value)}
                          className="h-8 px-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        />
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={loadingImpactId === act.id}
                          onClick={() => handleMeasureImpact(act.id)}
                        >
                          <BarChart3 className="w-3.5 h-3.5 text-indigo-600" />
                          <span>
                            {loadingImpactId === act.id
                              ? 'Đang tính...'
                              : 'Đo hiệu quả trước / sau'}
                          </span>
                        </Button>
                      </div>
                    </div>

                    {/* Impact Result Box */}
                    {impactData && (
                      <div className="p-4 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/60 space-y-2 text-xs">
                        <div className="font-bold text-slate-900 dark:text-white">
                          Kết quả đối chiếu trước và sau ngày {impactData.milestone_date || customSinceDate}
                        </div>
                        {impactData.status === 'insufficient_data' ? (
                          <p className="text-amber-700 dark:text-amber-300">
                            {impactData.note} (Trước: {impactData.pre_window?.total || 0} mẫu, Sau:{' '}
                            {impactData.post_window?.total || 0} mẫu). Bạn có thể chọn mốc ngày{' '}
                            <strong>2026-02-01</strong> để xem dữ liệu mẫu.
                          </p>
                        ) : (
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                              <div className="text-slate-400">Trước khi áp dụng</div>
                              <div className="font-bold text-rose-600 dark:text-rose-400 text-sm mt-0.5">
                                {impactData.pre_window?.neg_pct}% phàn nàn ({impactData.pre_window?.total} mẫu)
                              </div>
                            </div>
                            <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                              <div className="text-slate-400">Sau khi áp dụng</div>
                              <div className="font-bold text-emerald-600 dark:text-emerald-400 text-sm mt-0.5">
                                {impactData.post_window?.neg_pct}% phàn nàn ({impactData.post_window?.total} mẫu)
                              </div>
                            </div>
                            <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800">
                              <div className="text-slate-400">Mức thay đổi</div>
                              <div className="font-bold text-indigo-600 dark:text-indigo-400 text-sm mt-0.5">
                                {impactData.delta_pp > 0
                                  ? `Tăng +${impactData.delta_pp}%`
                                  : `Giảm ${impactData.delta_pp}%`}{' '}
                                ({impactData.status === 'improved' ? 'Cải thiện rõ rệt' : 'Chưa biến động lớn'})
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Row 3: Collapsible Technical Critic & Trace Info */}
      <Collapsible
        title="Chi tiết kỹ thuật: 7 quy tắc kiểm định tự động (R1–R7) & thông số chạy AI"
        badge={
          lastTrace ? (
            <Badge tone="success">
              Điểm kiểm định: {lastTrace.final_critic_score}/5.0 ({lastTrace.duration_ms}ms)
            </Badge>
          ) : null
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-1">
          {CRITIC_RULES_SUMMARY.map((r) => (
            <div
              key={r.id}
              className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/70 dark:border-slate-800 space-y-1"
            >
              <div className="flex items-center gap-1.5 font-bold text-indigo-600 dark:text-indigo-400">
                <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                <span>
                  {r.id}: {r.name}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                {r.desc}
              </p>
            </div>
          ))}
        </div>
      </Collapsible>

      {/* Edit / Reject Modal */}
      <DecisionModal
        isOpen={decisionModal.isOpen}
        onClose={() => setDecisionModal((prev) => ({ ...prev, isOpen: false }))}
        actionItem={decisionModal.actionItem}
        mode={decisionModal.mode}
        onSubmit={handleSubmitModalDecision}
        submitting={submittingDecision}
      />
    </div>
  );
}

// CreBy: MenBoyBMN
