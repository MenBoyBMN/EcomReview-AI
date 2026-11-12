export const ASPECT_META = {
  WATERPROOF: {
    label: 'Chống thấm nước',
    shortLabel: 'Chống thấm',
    code: 'WATERPROOF',
    color: '#3B82F6',
    desc: 'Độ kín nước đường may ép nhiệt, khóa kéo và tà áo khi đi mưa lớn',
  },
  MATERIAL_DURABILITY: {
    label: 'Chất liệu & Độ bền',
    shortLabel: 'Chất liệu',
    code: 'MATERIAL_DURABILITY',
    color: '#8B5CF6',
    desc: 'Chất vải dù tổ ong/da cá, độ dày, mùi nhựa và độ bền khuy bấm',
  },
  FIT_SIZE: {
    label: 'Kích cỡ & Độ vừa vặn',
    shortLabel: 'Kích cỡ',
    code: 'FIT_SIZE',
    color: '#EC4899',
    desc: 'Chiều dài, độ rộng tà áo khi ngồi xe máy hoặc đeo balo',
  },
  COMFORT_USABILITY: {
    label: 'Tiện dụng & Thoáng khí',
    shortLabel: 'Tiện dụng',
    code: 'COMFORT_USABILITY',
    color: '#10B981',
    desc: 'Kính chắn mưa, chụp gương chiếu hậu, độ thoáng khí và gấp gọn',
  },
  PRICE_VALUE: {
    label: 'Giá cả & Đáng tiền',
    shortLabel: 'Giá trị',
    code: 'PRICE_VALUE',
    color: '#F59E0B',
    desc: 'Mức giá bán so với chất lượng thực tế khách hàng nhận được',
  },
  PACKAGING_SHIPPING: {
    label: 'Đóng gói & Giao hàng',
    shortLabel: 'Giao hàng',
    code: 'PACKAGING_SHIPPING',
    color: '#06B6D4',
    desc: 'Tốc độ giao hàng, tình trạng túi đựng và hộp đóng gói',
  },
  CUSTOMER_SERVICE: {
    label: 'Chăm sóc khách hàng',
    shortLabel: 'CSKH',
    code: 'CUSTOMER_SERVICE',
    color: '#6366F1',
    desc: 'Thái độ tư vấn, tốc độ phản hồi tin nhắn và hỗ trợ đổi trả',
  },
  ACCESSIBILITY_DESIGN: {
    label: 'Màu sắc & Thiết kế',
    shortLabel: 'Thiết kế',
    code: 'ACCESSIBILITY_DESIGN',
    color: '#F43F5E',
    desc: 'Màu sắc thực tế so với ảnh chụp, kiểu dáng thời trang',
  },
  GENERAL: {
    label: 'Nhận xét chung',
    shortLabel: 'Chung',
    code: 'GENERAL',
    color: '#64748B',
    desc: 'Đánh giá tổng quát về sản phẩm và gian hàng',
  },
};

export const INSIGHT_KIND_META = {
  TOP_PAIN: {
    label: 'Điểm đau cần xử lý',
    shortLabel: 'Điểm đau',
    tone: 'danger',
    accentBorder: 'border-l-rose-500',
  },
  STRENGTH: {
    label: 'Điểm mạnh nổi bật',
    shortLabel: 'Điểm mạnh',
    tone: 'success',
    accentBorder: 'border-l-emerald-500',
  },
  HIDDEN_COMPLAINT: {
    label: 'Phàn nàn ẩn (4–5 sao)',
    shortLabel: 'Phàn nàn ẩn',
    tone: 'warning',
    accentBorder: 'border-l-amber-500',
  },
  PLATFORM_GAP: {
    label: 'Chênh lệch giữa 2 sàn',
    shortLabel: 'Chênh lệch sàn',
    tone: 'info',
    accentBorder: 'border-l-indigo-500',
  },
  EMERGING_ISSUE: {
    label: 'Vấn đề mới phát sinh',
    shortLabel: 'Vấn đề mới',
    tone: 'purple',
    accentBorder: 'border-l-purple-500',
  },
};

export const ACTION_TYPE_META = {
  LISTING_UPDATE: {
    label: 'Tối ưu gian hàng',
    category: 'Marketing',
    tone: 'info',
  },
  CONTENT: {
    label: 'Sản xuất nội dung / Video',
    category: 'Marketing',
    tone: 'purple',
  },
  CUSTOMER_CARE: {
    label: 'Chăm sóc khách hàng',
    category: 'Marketing',
    tone: 'info',
  },
  PROMOTION: {
    label: 'Chiến dịch ưu đãi',
    category: 'Marketing',
    tone: 'warning',
  },
  REVIEW_REPLY: {
    label: 'Phản hồi đánh giá',
    category: 'Marketing',
    tone: 'success',
  },
  PRODUCT_FIX: {
    label: 'Cải tiến sản phẩm',
    category: 'Vận hành & Sản phẩm',
    tone: 'danger',
  },
  OPS: {
    label: 'Quy trình kho & QC',
    category: 'Vận hành & Sản phẩm',
    tone: 'warning',
  },
};

export const STATUS_META = {
  PENDING: { label: 'Chờ duyệt', tone: 'warning' },
  APPROVED: { label: 'Đã duyệt', tone: 'success' },
  EDITED: { label: 'Đã chỉnh sửa', tone: 'info' },
  REJECTED: { label: 'Đã từ chối', tone: 'danger' },
};

export const EFFORT_LABELS = {
  LOW: 'Dễ làm ngay',
  MEDIUM: 'Trung bình',
  HIGH: 'Cần phối hợp',
};

export const IMPACT_LABELS = {
  HIGH: 'Tác động cao',
  MEDIUM: 'Tác động vừa',
  LOW: 'Tác động thấp',
};

export const CONFIDENCE_LABELS = {
  HIGH: 'Độ tin cậy cao',
  MEDIUM: 'Độ tin cậy vừa',
  LOW: 'Mẫu nhỏ',
  high: 'Độ tin cậy cao',
  medium: 'Độ tin cậy vừa',
  low: 'Mẫu nhỏ',
};

export const SCENARIO_OPTIONS = [
  { value: 'real_shop', label: 'real_shop · Dữ liệu thật Shop Áo Mưa (150)' },
  { value: 'S1', label: 'S1 · Thấm nước đường may' },
  { value: 'S2', label: 'S2 · Lệch size khi đeo balo' },
  { value: 'S3', label: 'S3 · Mùi nhựa & bung khuy bấm' },
  { value: 'S4', label: 'S4 · Phàn nàn ẩn trong đánh giá 5★' },
  { value: 'S5', label: 'S5 · Chênh lệch giao hàng Shopee vs TikTok' },
  { value: 'S6', label: 'S6 · Hiểu lầm màng nilon kính chắn mưa' },
  { value: 'S7', label: 'S7 · So sánh giá & độ đáng tiền' },
  { value: 'S8', label: 'S8 · Quá tải phản hồi CSKH mùa mưa' },
  { value: 'S9', label: 'S9 · Lệch màu thực tế so với ảnh' },
  { value: 'S10', label: 'S10 · Sản phẩm được khen toàn diện' },
];

export const CRITIC_RULES_SUMMARY = [
  { id: 'R1', name: 'Bằng chứng xác thực', desc: 'Mỗi đề xuất phải gắn kèm tối thiểu 2 mã đánh giá thực tế trong CSDL.' },
  { id: 'R2', name: 'Số liệu chính xác 100%', desc: 'Mọi con số thống kê trong lý do đề xuất phải khớp tuyệt đối với kết quả SQL.' },
  { id: 'R3', name: 'Đầy đủ 4 mục & thời hạn', desc: 'Có rõ việc cần làm, lý do, kênh thực hiện kèm thời hạn (24h, 48h, 72h...) và KPI.' },
  { id: 'R4', name: 'Không quảng cáo quá sự thật', desc: 'Cấm các cụm từ cam kết lố như "chống thấm 100%", "chống nước tuyệt đối".' },
  { id: 'R5', name: 'Đúng nhóm Marketing / Vận hành', desc: 'Phân loại chính xác việc của đội Marketing và việc của xưởng/kho.' },
  { id: 'R6', name: 'Không trùng lặp nội dung', desc: 'Các đề xuất trong cùng kế hoạch không bị lặp ý (Jaccard <= 0.80).' },
  { id: 'R7', name: 'Tuân thủ chính sách sàn', desc: 'Cấm tặng tiền đổi 5 sao hoặc kéo khách giao dịch ngoài Shopee / TikTok.' },
];

export function getAspectLabel(code) {
  return ASPECT_META[code]?.label || code || 'Tổng thể';
}

export function getAspectShortLabel(code) {
  return ASPECT_META[code]?.shortLabel || code || 'Chung';
}

// CreBy: MenBoyBMN
