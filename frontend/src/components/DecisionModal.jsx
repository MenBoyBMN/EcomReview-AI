import React, { useState, useEffect } from 'react';
import { Edit3, XCircle } from 'lucide-react';
import { Modal, Button } from './ui';

export default function DecisionModal({
  isOpen,
  onClose,
  actionItem,
  mode = 'EDITED', // 'EDITED' or 'REJECTED'
  onSubmit,
  submitting = false,
}) {
  const [editedContent, setEditedContent] = useState('');
  const [reasonCategory, setReasonCategory] = useState('refine_copywriting');
  const [note, setNote] = useState('');

  useEffect(() => {
    if (!actionItem) return;
    setEditedContent(actionItem.what_to_do || '');
    setNote('');
    setReasonCategory(mode === 'EDITED' ? 'refine_copywriting' : 'budget_constraint');
  }, [actionItem, mode, isOpen]);

  if (!isOpen || !actionItem) return null;

  const isEdit = mode === 'EDITED';

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      actionId: actionItem.id,
      decision: mode,
      edited_content: isEdit ? editedContent.trim() : '',
      reason_category: reasonCategory,
      note: note.trim(),
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      icon={isEdit ? Edit3 : XCircle}
      title={
        isEdit
          ? `Chỉnh sửa & phê duyệt hành động #${actionItem.id}`
          : `Từ chối đề xuất hành động #${actionItem.id}`
      }
      subtitle={actionItem.title}
      maxWidth="max-w-lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-sm">
        {isEdit && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Nội dung việc cần làm sau khi chỉnh sửa
            </label>
            <textarea
              rows={3}
              required
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              className="w-full p-3 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 leading-relaxed focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            {isEdit ? 'Lý do bạn điều chỉnh đề xuất này' : 'Lý do từ chối đề xuất này'}
          </label>
          <select
            value={reasonCategory}
            onChange={(e) => setReasonCategory(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          >
            <option value="refine_copywriting">Tinh chỉnh lại câu chữ cho phù hợp với Shop</option>
            <option value="adjust_scope">Điều chỉnh phạm vi hoặc thời hạn thực hiện</option>
            <option value="budget_constraint">Chưa đủ ngân sách / nhân sự thực hiện lúc này</option>
            <option value="already_done">Shop đã thực hiện việc này trước đó</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
            Ghi chú thêm cho đội ngũ (Tùy chọn)
          </label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Ví dụ: Giao bạn Lan thiết kế lại ảnh bảng size trước thứ 6..."
            className="w-full px-3 py-2 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" size="md" onClick={onClose}>
            Hủy
          </Button>
          <Button
            type="submit"
            variant={isEdit ? 'primary' : 'danger'}
            size="md"
            disabled={submitting}
          >
            {submitting
              ? 'Đang lưu...'
              : isEdit
              ? 'Lưu chỉnh sửa & Duyệt'
              : 'Xác nhận từ chối'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// CreBy: MenBoyBMN

