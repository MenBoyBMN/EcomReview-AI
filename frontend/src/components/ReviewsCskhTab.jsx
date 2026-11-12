import React, { useEffect, useState, useCallback } from 'react';
import {
  Search,
  Star,
  Bot,
  Sparkles,
  Copy,
  Check,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  UploadCloud,
  MessageSquareText,
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
  const [limit] = useState(15);
  const [offset, setOffset] = useState(0);

  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);

  // Reply assistant state mapped by review_id
  const [replyDrafts, setReplyDrafts] = useState({});
  const [loadingReplyId, setLoadingReplyId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  useEffect(() => {
    if (initialAspect) {
      setAspect(initialAspect);
      if (onClearInitialAspect) onClearInitialAspect();
    }
  }, [initialAspect, onClearInitialAspect]);

  const fetchReviews = useCallback(() => {
    setLoading(true);
    api
      .getReviews({
        scenarioTag,
        platform,
        aspect,
        polarity,
        reviewIds: searchId.trim(),
        limit,
        offset,
      })
      .then((res) => {
        setReviews(res.reviews || []);
      })
      .catch((err) => {
        showToast(err.message || 'Không thể tải danh sách đánh giá', 'error');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [scenarioTag, platform, aspect, polarity, searchId, limit, offset, showToast]);

  useEffect(() => {
    setOffset(0);
  }, [scenarioTag, platform, aspect, polarity, searchId]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews, refreshTrigger]);

  const handleGenerateReply = async (reviewId, mode = 'template') => {
    try {
      setLoadingReplyId(`${reviewId}_${mode}`);
      const res = await api.createReplyDraft(reviewId, scenarioTag, mode);
      setReplyDrafts((prev) => ({ ...prev, [reviewId]: res }));
      showToast(`Đã tạo câu trả lời CSKH cho đánh giá #${reviewId}!`, 'success');
    } catch (err) {
      showToast(err.message || 'Không thể tạo câu trả lời CSKH', 'error');
    } finally {
      setLoadingReplyId(null);
    }
  };

  const handleCopyReply = (reviewId, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(reviewId);
    showToast('Đã sao chép câu trả lời vào bộ nhớ tạm!', 'info');
    setTimeout(() => setCopiedId(null), 2000);
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
            <Button variant="primary" size="sm" onClick={onOpenUploadModal}>
              <UploadCloud className="w-4 h-4" />
              <span>Thêm đánh giá mới</span>
            </Button>
          }
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              placeholder="Tìm theo mã (VD: shp_0001)..."
              className="w-full h-9 pl-9 pr-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            />
          </div>

          <select
            aria-label="Chọn sàn thương mại điện tử"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="">Tất cả sàn (Shopee & TikTok)</option>
            <option value="shopee">Shopee</option>
            <option value="tiktok">TikTok Shop</option>
          </select>

          <select
            aria-label="Chọn khía cạnh sản phẩm"
            value={aspect}
            onChange={(e) => setAspect(e.target.value)}
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
            onChange={(e) => setPolarity(e.target.value)}
            className="h-9 px-3 text-xs sm:text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="">Mọi cảm xúc</option>
            <option value="negative">Phàn nàn (Tiêu cực)</option>
            <option value="positive">Khen ngợi (Tích cực)</option>
            <option value="neutral">Trung lập</option>
          </select>
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
            const draft = replyDrafts[rev.review_id];
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
                    <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                      #{rev.review_id}
                    </span>
                    <span className={isShopee ? 'badge-shopee' : 'badge-tiktok'}>
                      {isShopee ? 'Shopee' : 'TikTok Shop'}
                    </span>
                    <div
                      className="flex items-center gap-0.5 text-amber-400"
                      aria-label={`${rev.rating || 5} sao`}
                    >
                      {Array.from({ length: rev.rating || 5 }).map((_, idx) => (
                        <Star key={idx} className="w-3.5 h-3.5 fill-amber-400" />
                      ))}
                    </div>
                    <Badge tone={sentimentTone}>{sentimentLabel}</Badge>
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
                        <Badge tone="info">
                          <Bot className="w-3 h-3" /> Bản nháp phản hồi khách hàng
                        </Badge>
                        {draft.guardrail_report?.passed && (
                          <div className="flex items-center gap-1">
                            <Badge tone="success">
                              <ShieldCheck className="w-3 h-3" /> Đạt 6/6 quy tắc an toàn
                            </Badge>
                            <InfoTip text="Đã kiểm tra 6 quy tắc G1–G6: (1) Không cam kết quá đà, (2) Không mua chuộc đánh giá 5 sao, (3) Không lộ SĐT/link ngoài sàn, (4) Độ dài chuẩn 40–600 ký tự, (5) Giải đáp đúng điểm khách chê, (6) Không hứa bồi thường tiền trái phép." />
                          </div>
                        )}
                      </div>

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

                    <p className="text-sm text-slate-800 dark:text-slate-100 leading-relaxed bg-white dark:bg-slate-900 p-3.5 rounded-xl border border-slate-200/70 dark:border-slate-800">
                      {draft.reply_text}
                    </p>
                  </div>
                )}
              </Card>
            );
          })}

          {/* Clean Pagination Bar */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-500 tabular-nums">
              Trang {currentPage} • Hiển thị {offset + 1} – {offset + reviews.length} đánh giá
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
                disabled={reviews.length < limit}
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
