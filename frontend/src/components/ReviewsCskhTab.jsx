import React, { useEffect, useState, useCallback } from 'react';
import {
  Search,
  Star,
  Bot,
  Sparkles,
  Copy,
  Check,
  CheckCircle2,
  Send,
  History,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  UploadCloud,
  MessageSquareText,
  Pencil,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api/client';
import { ASPECT_META, getAspectLabel, getAspectShortLabel } from '../constants/taxonomy';
import {
  Card,
  SectionHeader,
  Button,
  Badge,
  EmptyState,
  InfoTip,
} from './ui';

export default function ReviewsCskhTab({
  scenarioTag,
  userRole = 'owner',
  initialAspect = '',
  onClearInitialAspect,
  onOpenUploadModal,
  showToast,
  refreshTrigger,
}) {
  const [platform, setPlatform] = useState('');
  const [aspect, setAspect] = useState(initialAspect || '');
  const [polarity, setPolarity] = useState('');
  const [searchId, setSearchId] = useState('');
  const [debouncedSearchId, setDebouncedSearchId] = useState('');
  const [limit] = useState(15);
  const [offset, setOffset] = useState(0);

  const [reviews, setReviews] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);

  // Reply assistant state mapped by review_id
  const [replyDrafts, setReplyDrafts] = useState({});
  const [replyHistoryMap, setReplyHistoryMap] = useState({});
  const [openHistoryIds, setOpenHistoryIds] = useState(() => new Set());
  const [loadingReplyId, setLoadingReplyId] = useState(null);
  const [updatingStatusId, setUpdatingStatusId] = useState(null);
  const [editingReplyId, setEditingReplyId] = useState(null);
  const [editedReplyText, setEditedReplyText] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [syncingMarket, setSyncingMarket] = useState(false);
  const [anomalyOnly, setAnomalyOnly] = useState(false);
  const [selectedReviewIds, setSelectedReviewIds] = useState(() => new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    setOffset(0);
    setReplyDrafts({});
    setReplyHistoryMap({});
    setOpenHistoryIds(new Set());
    setSelectedReviewIds(new Set());
    setEditingReplyId(null);
    setEditedReplyText('');
  }, [scenarioTag]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchId(searchId.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchId]);

  useEffect(() => {
    if (initialAspect) {
      setAspect(initialAspect);
      setOffset(0);
      if (onClearInitialAspect) onClearInitialAspect();
    }
  }, [initialAspect, onClearInitialAspect]);

  const fetchReviews = useCallback(() => {
    let active = true;
    setLoading(true);
    api
      .getReviews({
        scenarioTag,
        platform,
        aspect,
        polarity,
        anomalyOnly,
        reviewIds: debouncedSearchId,
        limit,
        offset,
      })
      .then((res) => {
        if (active) {
          const items = res.reviews || [];
          setReviews(items);
          setTotalCount(res.total_count ?? items.length);
        }
      })
      .catch((err) => {
        if (active) showToast(err.message || 'Không thể tải danh sách đánh giá', 'error');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    scenarioTag,
    platform,
    aspect,
    polarity,
    anomalyOnly,
    debouncedSearchId,
    limit,
    offset,
    showToast,
  ]);

  useEffect(() => {
    const cancel = fetchReviews();
    return () => {
      if (cancel) cancel();
    };
  }, [fetchReviews, refreshTrigger]);

  const handleGenerateReply = async (reviewId, mode = 'template') => {
    try {
      setLoadingReplyId(`${reviewId}_${mode}`);
      const res = await api.createReplyDraft(reviewId, scenarioTag, mode);
      setReplyDrafts((prev) => ({ ...prev, [reviewId]: res }));
      setReviews((prev) =>
        prev.map((r) =>
          r.review_id === reviewId ? { ...r, reply_status: res.status || 'DRAFT', latest_reply: res } : r
        )
      );
      if (openHistoryIds.has(reviewId)) {
        const histRes = await api.getReviewReplies(reviewId, scenarioTag).catch(() => null);
        if (histRes) {
          setReplyHistoryMap((prev) => ({ ...prev, [reviewId]: histRes.replies || [] }));
        }
      } else {
        setReplyHistoryMap((prev) => {
          if (!(reviewId in prev)) return prev;
          const next = { ...prev };
          delete next[reviewId];
          return next;
        });
      }
      showToast(`Đã tạo câu trả lời CSKH cho đánh giá #${reviewId}!`, 'success');
    } catch (err) {
      showToast(err.message || 'Không thể tạo câu trả lời CSKH', 'error');
    } finally {
      setLoadingReplyId(null);
    }
  };

  const handleUpdateReplyStatus = async (reviewId, replyId, nextStatus, replyText = null) => {
    try {
      setUpdatingStatusId(replyId);
      const updated = await api.updateReplyStatus(replyId, nextStatus, replyText);
      const normalized = {
        reply_id: updated.id,
        reply_text: updated.reply_text,
        mode_used: updated.mode_used,
        guardrail_report: {
          passed: updated.guardrail_passed,
          violations: updated.violations || [],
        },
        status: updated.status,
        created_by: updated.created_by,
        created_at: updated.created_at,
        sent_at: updated.sent_at,
        external_sync_status: updated.external_sync_status || 'LOCAL_ONLY',
        external_sync_error: updated.external_sync_error || null,
        external_synced_at: updated.external_synced_at || null,
      };
      setReplyDrafts((prev) => ({ ...prev, [reviewId]: normalized }));
      setReviews((prev) =>
        prev.map((r) =>
          r.review_id === reviewId
            ? { ...r, reply_status: updated.status, latest_reply: normalized }
            : r
        )
      );
      if (openHistoryIds.has(reviewId)) {
        const histRes = await api.getReviewReplies(reviewId, scenarioTag).catch(() => null);
        if (histRes) {
          setReplyHistoryMap((prev) => ({ ...prev, [reviewId]: histRes.replies || [] }));
        }
      } else {
        setReplyHistoryMap((prev) => {
          if (!(reviewId in prev)) return prev;
          const next = { ...prev };
          delete next[reviewId];
          return next;
        });
      }
      if (replyText !== null) {
        setEditingReplyId(null);
        setEditedReplyText('');
        showToast(`Đã cập nhật & kiểm duyệt G1–G6 phản hồi cho #${reviewId}!`, 'success');
      } else {
        showToast(
          nextStatus === 'SENT'
            ? `Đã đánh dấu đã gửi phản hồi cho #${reviewId}!`
            : `Đã duyệt nháp phản hồi cho #${reviewId}!`,
          'success'
        );
      }
    } catch (err) {
      showToast(err.message || 'Không thể cập nhật trạng thái phản hồi', 'error');
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const handleToggleHistory = async (reviewId) => {
    const isOpen = openHistoryIds.has(reviewId);
    if (isOpen) {
      setOpenHistoryIds((prev) => {
        const next = new Set(prev);
        next.delete(reviewId);
        return next;
      });
      return;
    }
    try {
      const res = await api.getReviewReplies(reviewId, scenarioTag);
      setReplyHistoryMap((prev) => ({ ...prev, [reviewId]: res.replies || [] }));
      setOpenHistoryIds((prev) => new Set(prev).add(reviewId));
    } catch (err) {
      showToast(err.message || 'Không thể tải lịch sử phản hồi', 'error');
    }
  };

  const handleCopyReply = async (reviewId, text) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopiedId(reviewId);
      showToast('Đã sao chép câu trả lời vào bộ nhớ tạm!', 'info');
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      showToast('Không thể sao chép vào bộ nhớ tạm', 'error');
    }
  };

  const handleSyncMarketplace = async () => {
    try {
      setSyncingMarket(true);
      const res = await api.getShopConnectors(scenarioTag);
      const active = res?.connections || [];
      if (active.length === 0) {
        showToast('Chưa có kết nối Shopee/TikTok. Hãy cấu hình trong mục Kết nối Sàn.', 'info');
        return;
      }
      await Promise.all(active.map((c) => api.syncShopConnector(scenarioTag, c.platform, {})));
      showToast(`Đã đồng bộ đánh giá mới từ ${active.length} sàn kết nối!`, 'success');
      fetchReviews();
    } catch (err) {
      showToast(err.message || 'Đồng bộ đánh giá từ sàn thất bại', 'error');
    } finally {
      setSyncingMarket(false);
    }
  };

  const handleRetryPush = async (reviewId, replyId) => {
    try {
      setUpdatingStatusId(replyId);
      const updated = await api.retryPushReply(replyId);
      setReviews((prev) =>
        prev.map((r) =>
          r.review_id === reviewId
            ? {
                ...r,
                latest_reply: {
                  ...(r.latest_reply || {}),
                  external_sync_status: updated.external_sync_status,
                  external_sync_error: updated.external_sync_error || null,
                },
              }
            : r
        )
      );
      showToast('Đã gửi lại yêu cầu đẩy phản hồi lên sàn!', 'success');
    } catch (err) {
      showToast(err.message || 'Không thể đẩy phản hồi lên sàn', 'error');
    } finally {
      setUpdatingStatusId(null);
    }
  };

  const handleToggleSelectReview = (reviewId) => {
    setSelectedReviewIds((prev) => {
      const next = new Set(prev);
      if (next.has(reviewId)) next.delete(reviewId);
      else next.add(reviewId);
      return next;
    });
  };

  const handleSelectAllPage = () => {
    if (selectedReviewIds.size === reviews.length && reviews.length > 0) {
      setSelectedReviewIds(new Set());
    } else {
      setSelectedReviewIds(new Set(reviews.map((r) => r.review_id)));
    }
  };

  const handleBulkDraft = async () => {
    const ids = Array.from(selectedReviewIds);
    if (ids.length === 0) return;
    try {
      setBulkBusy(true);
      const res = await api.bulkCreateReplyDrafts({
        scenario_tag: scenarioTag,
        review_ids: ids.slice(0, 50),
        mode: 'template',
      });
      showToast(`Đã tạo ${res.created_count || 0} bản nháp CSKH hàng loạt!`, 'success');
      setSelectedReviewIds(new Set());
      fetchReviews();
    } catch (err) {
      showToast(err.message || 'Không thể tạo nháp hàng loạt', 'error');
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkSend = async () => {
    const replyIds = reviews
      .filter((r) => selectedReviewIds.has(r.review_id))
      .map((r) => (replyDrafts[r.review_id] || r.latest_reply)?.reply_id)
      .filter(Boolean);
    if (replyIds.length === 0) {
      showToast('Các đánh giá đã chọn chưa có bản nháp. Hãy tạo nháp trước!', 'info');
      return;
    }
    try {
      setBulkBusy(true);
      const res = await api.bulkUpdateReplyStatus({
        scenario_tag: scenarioTag,
        reply_ids: replyIds.slice(0, 50),
        status: 'SENT',
        push_to_marketplace: true,
      });
      showToast(`Đã duyệt & gửi ${res.updated_count || 0} phản hồi hàng loạt!`, 'success');
      setSelectedReviewIds(new Set());
      fetchReviews();
    } catch (err) {
      showToast(err.message || 'Không thể gửi phản hồi hàng loạt', 'error');
    } finally {
      setBulkBusy(false);
    }
  };

  const handleAutoReply5Star = async () => {
    try {
      setBulkBusy(true);
      const res = await api.triggerAutoReply5Star({
        scenario_tag: scenarioTag,
        limit: 50,
        push_to_marketplace: true,
      });
      showToast(
        `Đã tự động trả lời ${res.replied_count || 0} đánh giá 5★ sạch (bỏ qua ${res.skipped_count || 0} bài)!`,
        'success'
      );
      fetchReviews();
    } catch (err) {
      showToast(err.message || 'Auto-reply 5★ thất bại', 'error');
    } finally {
      setBulkBusy(false);
    }
  };

  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="space-y-5">
      {/* Filter Bar */}
      <Card className="space-y-4">
        <SectionHeader
          icon={MessageSquareText}
          title="Tra cứu đánh giá & soạn phản hồi chăm sóc khách hàng"
          subtitle="Lọc đánh giá theo sàn hoặc khía cạnh và dùng trợ lý AI để soạn câu trả lời lịch sự, đúng quy định sàn"
          actions={
            userRole !== 'cskh' && (
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={bulkBusy}
                  onClick={handleAutoReply5Star}
                >
                  <Sparkles className="w-4 h-4 text-amber-500" />
                  <span>Auto-reply 5★</span>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={syncingMarket}
                  onClick={handleSyncMarketplace}
                >
                  <RefreshCw className={`w-4 h-4 ${syncingMarket ? 'animate-spin' : ''}`} />
                  <span>{syncingMarket ? 'Đang đồng bộ...' : 'Đồng bộ sàn'}</span>
                </Button>
                <Button variant="primary" size="sm" onClick={onOpenUploadModal}>
                  <UploadCloud className="w-4 h-4" />
                  <span>Thêm đánh giá mới</span>
                </Button>
              </div>
            )
          }
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchId}
              onChange={(e) => {
                setSearchId(e.target.value);
                setOffset(0);
              }}
              placeholder="Tìm theo mã (VD: shp_0001)..."
              className="w-full h-9 pl-9 pr-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
          </div>

          <select
            aria-label="Chọn sàn thương mại điện tử"
            value={platform}
            onChange={(e) => {
              setPlatform(e.target.value);
              setOffset(0);
            }}
            className="h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="">Tất cả sàn (Shopee & TikTok)</option>
            <option value="shopee">Shopee</option>
            <option value="tiktok">TikTok Shop</option>
          </select>

          <select
            aria-label="Chọn khía cạnh sản phẩm"
            value={aspect}
            onChange={(e) => {
              setAspect(e.target.value);
              setOffset(0);
            }}
            className="h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="">Tất cả 8 khía cạnh</option>
            {Object.keys(ASPECT_META)
              .filter((k) => k !== 'GENERAL')
              .map((k) => (
                <option key={k} value={k}>
                  {getAspectLabel(k)}
                </option>
              ))}
          </select>

          <select
            aria-label="Chọn sắc thái cảm xúc"
            value={polarity}
            onChange={(e) => {
              setPolarity(e.target.value);
              setOffset(0);
            }}
            className="h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="">Mọi cảm xúc</option>
            <option value="negative">Phàn nàn (Tiêu cực)</option>
            <option value="positive">Khen ngợi (Tích cực)</option>
            <option value="neutral">Trung lập</option>
          </select>
        </div>

        <div className="flex items-center justify-between flex-wrap gap-2 pt-1 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-3 flex-wrap text-xs">
            <label className="inline-flex items-center gap-1.5 cursor-pointer text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={anomalyOnly}
                onChange={(e) => {
                  setAnomalyOnly(e.target.checked);
                  setOffset(0);
                }}
                className="rounded border-slate-300 text-indigo-600"
              />
              <span>Chỉ xem đánh giá bất thường (Spam / Seeding / Chê ẩn)</span>
            </label>
            {reviews.length > 0 && (
              <button
                type="button"
                onClick={handleSelectAllPage}
                className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
              >
                {selectedReviewIds.size === reviews.length
                  ? 'Bỏ chọn trang này'
                  : `Chọn cả ${reviews.length} bài trên trang`}
              </button>
            )}
          </div>

          {selectedReviewIds.size > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                Đã chọn {selectedReviewIds.size}
              </span>
              <Button variant="secondary" size="sm" disabled={bulkBusy} onClick={handleBulkDraft}>
                Tạo nháp hàng loạt
              </Button>
              <Button variant="primary" size="sm" disabled={bulkBusy} onClick={handleBulkSend}>
                Duyệt & Gửi hàng loạt
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Reviews List */}
      {loading ? (
        <Card>
          <div className="py-12 text-center text-sm text-slate-400">
            Đang tải danh sách đánh giá khách hàng...
          </div>
        </Card>
      ) : reviews.length === 0 ? (
        <Card>
          <EmptyState
            icon={Search}
            title="Không tìm thấy đánh giá nào phù hợp"
            description="Hãy thử xóa bớt bộ lọc hoặc chọn Tất cả 8 khía cạnh."
            action={
              (platform || aspect || polarity || searchId) && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setPlatform('');
                    setAspect('');
                    setPolarity('');
                    setSearchId('');
                    setOffset(0);
                  }}
                >
                  Đặt lại bộ lọc
                </Button>
              )
            }
          />
        </Card>
      ) : (
        <div className="space-y-3.5">
          {reviews.map((rev) => {
            const draft = replyDrafts[rev.review_id] || rev.latest_reply;
            const replyHistory = replyHistoryMap[rev.review_id] || [];
            const isHistoryOpen = openHistoryIds.has(rev.review_id);
            const isShopee = (rev.platform || '').toLowerCase() === 'shopee';
            const sentimentTone =
              rev.overall_sentiment === 'negative'
                ? 'danger'
                : rev.overall_sentiment === 'positive'
                ? 'success'
                : 'neutral';
            const sentimentLabel =
              rev.overall_sentiment === 'negative'
                ? 'Phàn nàn'
                : rev.overall_sentiment === 'positive'
                ? 'Khen ngợi'
                : 'Trung lập';

            return (
              <Card key={rev.review_id} className="space-y-3">
                {/* Top Header */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <input
                      type="checkbox"
                      aria-label={`Chọn đánh giá ${rev.review_id}`}
                      checked={selectedReviewIds.has(rev.review_id)}
                      onChange={() => handleToggleSelectReview(rev.review_id)}
                      className="rounded border-slate-300 text-indigo-600"
                    />
                    <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                      #{rev.review_id}
                    </span>
                    <span className={isShopee ? 'badge-shopee' : 'badge-tiktok'}>
                      {isShopee ? 'Shopee' : 'TikTok Shop'}
                    </span>
                    {rev.variation && (
                      <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                        {rev.variation}
                      </span>
                    )}
                    {(rev.anomaly_flags || []).map((flag) => (
                      <Badge key={flag} tone="warning">
                        {flag === 'SPAM_REPEATED_CHARS'
                          ? 'Spam ký tự'
                          : flag === 'SEEDING_DUPLICATE'
                          ? 'Nghi seeding'
                          : 'Chê ẩn 4–5★'}
                      </Badge>
                    ))}
                    <div
                      className="flex items-center gap-0.5 text-amber-400"
                      aria-label={`${rev.rating || 5} sao`}
                    >
                      {Array.from({ length: rev.rating || 5 }).map((_, idx) => (
                        <Star key={idx} className="w-3.5 h-3.5 fill-amber-400" />
                      ))}
                    </div>
                    <Badge tone={sentimentTone}>{sentimentLabel}</Badge>
                    {rev.sla_overdue && (
                      <Badge tone="danger">Quá hạn SLA 24h</Badge>
                    )}
                    {rev.reply_status && rev.reply_status !== 'NONE' && (
                      <Badge tone="info">Đã có nháp CSKH ({rev.reply_status})</Badge>
                    )}
                    {rev.created_at && (
                      <span className="text-xs text-slate-400 tabular-nums">
                        {rev.created_at.slice(0, 10)}
                      </span>
                    )}
                  </div>

                  {/* Reply Buttons */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={loadingReplyId === `${rev.review_id}_template`}
                      onClick={() => handleGenerateReply(rev.review_id, 'template')}
                    >
                      <Bot className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      <span>
                        {loadingReplyId === `${rev.review_id}_template`
                          ? 'Đang soạn...'
                          : 'Soạn trả lời mẫu'}
                      </span>
                    </Button>

                    <Button
                      variant="primary"
                      size="sm"
                      disabled={loadingReplyId === `${rev.review_id}_llm`}
                      onClick={() => handleGenerateReply(rev.review_id, 'llm')}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>
                        {loadingReplyId === `${rev.review_id}_llm`
                          ? 'AI đang viết...'
                          : 'AI viết trả lời'}
                      </span>
                    </Button>
                  </div>
                </div>

                {/* Review Text */}
                <p className="text-sm text-slate-800 dark:text-slate-100 leading-relaxed">
                  “{rev.text_raw}”
                </p>

                {/* Extracted ABSA Opinions */}
                {rev.opinions && rev.opinions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {rev.opinions.map((op, i) => {
                      const tone =
                        op.polarity === 'negative'
                          ? 'danger'
                          : op.polarity === 'positive'
                          ? 'success'
                          : 'neutral';
                      return (
                        <Badge key={i} tone={tone}>
                          <strong>{getAspectShortLabel(op.aspect)}:</strong> “{op.evidence}”
                        </Badge>
                      );
                    })}
                  </div>
                )}

                {/* Generated CSKH Reply Draft */}
                {draft && (
                  <div className="mt-2 p-4 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/60 space-y-2.5 animate-fade-in">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge
                          tone={
                            draft.status === 'SENT'
                              ? 'success'
                              : draft.status === 'APPROVED'
                              ? 'info'
                              : 'neutral'
                          }
                        >
                          <Bot className="w-3 h-3" />{' '}
                          {draft.status === 'SENT'
                            ? 'Đã gửi khách'
                            : draft.status === 'APPROVED'
                            ? 'Đã duyệt nháp'
                            : 'Bản nháp CSKH'}
                        </Badge>
                        {draft.guardrail_report?.passed === false ? (
                          <div className="flex items-center gap-1">
                            <Badge tone="danger">
                              Chưa đạt quy tắc an toàn ({draft.guardrail_report.violations?.join(', ') || 'Vi phạm'})
                            </Badge>
                          </div>
                        ) : draft.guardrail_report?.passed ? (
                          <div className="flex items-center gap-1">
                            <Badge tone="success">
                              <ShieldCheck className="w-3 h-3" /> Đạt 6/6 quy tắc an toàn
                            </Badge>
                            <InfoTip text="Đã kiểm tra 6 quy tắc G1–G6: (1) Không cam kết quá đà, (2) Không mua chuộc đánh giá 5 sao, (3) Không lộ SĐT/link ngoài sàn, (4) Độ dài chuẩn 40–600 ký tự, (5) Giải đáp đúng điểm khách chê, (6) Không hứa bồi thường tiền trái phép." />
                          </div>
                        ) : null}
                        {draft.external_sync_status === 'PUSHED' && (
                          <Badge tone="success">Đã đẩy lên sàn</Badge>
                        )}
                        {draft.external_sync_status === 'QUEUED' && (
                          <Badge tone="info">Đang đẩy lên sàn</Badge>
                        )}
                        {draft.external_sync_status === 'FAILED' && (
                          <div className="flex items-center gap-1.5">
                            <Badge tone="danger" title={draft.external_sync_error || ''}>
                              Đẩy sàn lỗi
                            </Badge>
                            {draft.reply_id && (
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={updatingStatusId === draft.reply_id}
                                onClick={() => handleRetryPush(rev.review_id, draft.reply_id)}
                              >
                                <RefreshCw className="w-3 h-3" />
                                <span>Thử đẩy lại</span>
                              </Button>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 flex-wrap">
                        {draft.reply_id && draft.status !== 'SENT' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={updatingStatusId === draft.reply_id}
                            onClick={() => {
                              setEditingReplyId(draft.reply_id);
                              setEditedReplyText(draft.reply_text || '');
                            }}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                            <span>Sửa nháp</span>
                          </Button>
                        )}
                        {draft.reply_id && draft.status === 'DRAFT' && (
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={
                              updatingStatusId === draft.reply_id ||
                              draft.guardrail_report?.passed === false
                            }
                            title={
                              draft.guardrail_report?.passed === false
                                ? 'Bản nháp chưa đạt quy tắc an toàn G1–G6, hãy sửa trước khi duyệt'
                                : undefined
                            }
                            onClick={() =>
                              handleUpdateReplyStatus(rev.review_id, draft.reply_id, 'APPROVED')
                            }
                          >
                            <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600" />
                            <span>Duyệt nháp</span>
                          </Button>
                        )}
                        {draft.reply_id && draft.status !== 'SENT' && (
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={
                              updatingStatusId === draft.reply_id ||
                              draft.guardrail_report?.passed === false
                            }
                            title={
                              draft.guardrail_report?.passed === false
                                ? 'Bản nháp chưa đạt quy tắc an toàn G1–G6, hãy sửa trước khi gửi'
                                : 'Sao chép nội dung vào clipboard và đánh dấu đã gửi'
                            }
                            onClick={async () => {
                              await handleCopyReply(rev.review_id, draft.reply_text);
                              await handleUpdateReplyStatus(rev.review_id, draft.reply_id, 'SENT');
                            }}
                          >
                            <Send className="w-3.5 h-3.5" />
                            <span>Sao chép & Đánh dấu đã gửi</span>
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleHistory(rev.review_id)}
                        >
                          <History className="w-3.5 h-3.5" />
                          <span>{isHistoryOpen ? 'Ẩn lịch sử' : 'Lịch sử nháp'}</span>
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleCopyReply(rev.review_id, draft.reply_text)}
                        >
                          {copiedId === rev.review_id ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                              <span>Đã sao chép</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5 text-slate-500" />
                              <span>Sao chép câu trả lời</span>
                            </>
                          )}
                        </Button>
                      </div>
                    </div>

                    {editingReplyId === draft.reply_id ? (
                      <div className="space-y-2">
                        <textarea
                          rows={3}
                          value={editedReplyText}
                          onChange={(e) => setEditedReplyText(e.target.value)}
                          className="w-full text-sm text-slate-800 dark:text-slate-100 leading-relaxed bg-white dark:bg-slate-900 p-3 rounded-xl border border-indigo-300 dark:border-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          placeholder="Nhập nội dung phản hồi CSKH (40–600 ký tự, tuân thủ G1–G6)..."
                        />
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] text-slate-400">
                            {editedReplyText.trim().length}/600 ký tự
                          </span>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setEditingReplyId(null);
                                setEditedReplyText('');
                              }}
                            >
                              Hủy
                            </Button>
                            <Button
                              variant="primary"
                              size="sm"
                              disabled={
                                updatingStatusId === draft.reply_id || !editedReplyText.trim()
                              }
                              onClick={() =>
                                handleUpdateReplyStatus(
                                  rev.review_id,
                                  draft.reply_id,
                                  draft.status || 'DRAFT',
                                  editedReplyText.trim()
                                )
                              }
                            >
                              Lưu & Kiểm duyệt
                            </Button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-slate-800 dark:text-slate-100 leading-relaxed bg-white dark:bg-slate-900 p-3.5 rounded-xl border border-slate-200/70 dark:border-slate-800">
                        {draft.reply_text}
                      </p>
                    )}

                    {(draft.created_at || draft.sent_at) && (
                      <div className="text-[11px] text-slate-400 flex items-center gap-3 flex-wrap">
                        {draft.created_at && (
                          <span>Tạo lúc: {String(draft.created_at).slice(0, 19).replace('T', ' ')}</span>
                        )}
                        {draft.sent_at && (
                          <span>Đã gửi lúc: {String(draft.sent_at).slice(0, 19).replace('T', ' ')}</span>
                        )}
                      </div>
                    )}

                    {isHistoryOpen &&
                      (replyHistory.length > 0 ? (
                        <div className="pt-2 border-t border-indigo-200/70 dark:border-indigo-800/50 space-y-1.5">
                          <div className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                            Lịch sử phản hồi đã lưu ({replyHistory.length} phiên bản)
                          </div>
                          <div className="space-y-1.5 max-h-40 overflow-y-auto">
                            {replyHistory.map((h) => (
                              <div
                                key={h.id}
                                className="p-2 rounded-lg bg-white/80 dark:bg-slate-900/70 border border-slate-200/70 dark:border-slate-800 text-xs space-y-1"
                              >
                                <div className="flex items-center justify-between text-[11px] text-slate-400">
                                  <span>
                                    #{h.id} • {h.status} • {h.mode_used}
                                  </span>
                                  <span>{String(h.created_at || '').slice(0, 19).replace('T', ' ')}</span>
                                </div>
                                <p className="text-slate-700 dark:text-slate-300">{h.reply_text}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="pt-2 border-t border-indigo-200/70 dark:border-indigo-800/50 text-xs text-slate-400">
                          Chưa có phiên bản nháp nào trước đó.
                        </div>
                      ))}
                  </div>
                )}
              </Card>
            );
          })}

          {/* Clean Pagination Bar */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-500 tabular-nums">
              Trang {currentPage} / {Math.max(1, Math.ceil(totalCount / limit))} • Hiển thị{' '}
              {offset + 1} – {offset + reviews.length} / {totalCount} đánh giá
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Trang trước</span>
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={totalCount > 0 ? offset + limit >= totalCount : reviews.length < limit}
                onClick={() => setOffset((prev) => prev + limit)}
              >
                <span>Trang tiếp</span>
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// CreBy: MenBoyBMN
