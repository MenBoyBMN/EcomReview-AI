import React, { useEffect, useState } from 'react';
import { Star, MessageSquareText } from 'lucide-react';
import { api } from '../api/client';
import { getAspectLabel } from '../constants/taxonomy';
import { Modal, Button, Badge } from './ui';

export default function EvidenceModal({
  isOpen,
  onClose,
  scenarioTag,
  reviewIds = [],
  contextTitle = '',
}) {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen || !reviewIds || reviewIds.length === 0) return;
    let active = true;
    setLoading(true);
    setError('');

    api
      .getReviews({
        scenarioTag,
        reviewIds: reviewIds.join(','),
        limit: 50,
      })
      .then((res) => {
        if (active) setReviews(res.reviews || []);
      })
      .catch((err) => {
        if (active) setError(err.message || 'Không thể tải đánh giá gốc');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, scenarioTag, reviewIds]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={MessageSquareText}
      title="Đánh giá gốc của khách hàng (Bằng chứng xác thực)"
      subtitle={contextTitle}
      maxWidth="max-w-2xl"
      footer={
        <>
          <span className="text-xs text-slate-500">
            Hiển thị {reviews.length} đánh giá thực tế từ cơ sở dữ liệu
          </span>
          <Button variant="primary" size="sm" onClick={onClose}>
            Đóng
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="py-10 text-center text-sm text-slate-500">
          Đang tải {reviewIds.length} đánh giá gốc...
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 text-xs">
          {error}
        </div>
      ) : reviews.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-500">
          Không tìm thấy đánh giá khớp với mã [{reviewIds.join(', ')}].
        </div>
      ) : (
        <div className="space-y-3">
          {reviews.map((rev) => {
            const isShopee = (rev.platform || '').toLowerCase() === 'shopee';
            return (
              <div
                key={rev.review_id}
                className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 space-y-2.5"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                      #{rev.review_id}
                    </span>
                    <span className={isShopee ? 'badge-shopee' : 'badge-tiktok'}>
                      {isShopee ? 'Shopee' : 'TikTok Shop'}
                    </span>
                    <div className="flex items-center gap-0.5 text-amber-400">
                      {Array.from({ length: rev.rating || 5 }).map((_, i) => (
                        <Star key={i} className="w-3.5 h-3.5 fill-amber-400" />
                      ))}
                    </div>
                  </div>
                  {rev.created_at && (
                    <span className="text-xs text-slate-400 tabular-nums">
                      {rev.created_at.slice(0, 10)}
                    </span>
                  )}
                </div>

                <p className="text-sm text-slate-800 dark:text-slate-100 leading-relaxed">
                  “{rev.text_raw}”
                </p>

                {rev.opinions && rev.opinions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {rev.opinions.map((op, idx) => {
                      const tone =
                        op.polarity === 'negative'
                          ? 'danger'
                          : op.polarity === 'positive'
                          ? 'success'
                          : 'neutral';
                      return (
                        <Badge key={idx} tone={tone}>
                          <strong>{getAspectLabel(op.aspect)}:</strong> “{op.evidence}”
                        </Badge>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}

// CreBy: MenBoyBMN
