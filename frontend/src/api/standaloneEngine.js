import { getAspectLabel } from '../constants/taxonomy';

const STORAGE_KEY = 'ecomreview_standalone_state_v1';

const ASPECT_KEYWORDS = {
  WATERPROOF: ['thấm', 'nước', 'mưa', 'đường may', 'ướt', 'dột', 'seam', 'chống thấm'],
  MATERIAL_DURABILITY: ['vải', 'chất liệu', 'bền', 'rách', 'khóa', 'nút', 'cúc', 'dày', 'mỏng', 'mùi nhựa'],
  FIT_SIZE: ['size', 'kích', 'cỡ', 'rộng', 'chật', 'dài', 'ngắn', 'balo', 'vừa'],
  COMFORT_USABILITY: ['tiện', 'gấp', 'bí', 'mũ', 'kính', 'thoáng', 'vướng', 'chụp gương'],
  PRICE_VALUE: ['giá', 'tiền', 'đắt', 'rẻ', 'đáng', 'hời'],
  PACKAGING_SHIPPING: ['giao', 'ship', 'đóng gói', 'hộp', 'túi', 'vận chuyển', 'nhanh', 'chậm'],
  CUSTOMER_SERVICE: ['tư vấn', 'cskh', 'chăm sóc', 'hỗ trợ', 'tin nhắn', 'thái độ', 'đổi trả'],
  ACCESSIBILITY_DESIGN: ['màu', 'mẫu', 'kiểu', 'đẹp', 'dáng', 'phản quang', 'thời trang'],
  GENERAL: ['phản hồi', 'góp ý', 'ghi nhận', 'trải nghiệm', 'hỗ trợ'],
};

const NEGATIVE_CUES = [
  'thấm', 'ướt', 'rách', 'mỏng', 'hỏng', 'bung', 'kẹt', 'chật', 'ngắn',
  'mùi', 'bí', 'mờ', 'chậm', 'lâu', 'tệ', 'kém', 'thất vọng', 'lỗi', 'sai màu', 'đắt',
];

const ASPECT_SHORT_PHRASES = {
  WATERPROOF: 'chống thấm nước',
  MATERIAL_DURABILITY: 'chất liệu vải & độ bền',
  FIT_SIZE: 'kích cỡ size',
  COMFORT_USABILITY: 'độ tiện dụng thoáng khí',
  PRICE_VALUE: 'giá cả',
  PACKAGING_SHIPPING: 'đóng gói & giao hàng',
  CUSTOMER_SERVICE: 'chăm sóc hỗ trợ',
  ACCESSIBILITY_DESIGN: 'màu sắc & kiểu dáng',
  GENERAL: 'trải nghiệm chung',
};

const REPLY_TEMPLATES = {
  greeting: 'Dạ Shop Áo Mưa xin chân thành cảm ơn Quý khách đã ủng hộ và gửi phản hồi cho sản phẩm.',
  closing: 'Chúc Quý khách luôn có những chuyến đi bình an và an tâm trong mùa mưa này ạ!',
  aspect_handlers: {
    WATERPROOF:
      'Về vấn đề thấm nước hoặc đường may, Shop rất lấy làm tiếc vì sản phẩm chưa đạt kỳ vọng khi di chuyển mưa to. Shop xin phép hỗ trợ bảo hành đổi mới 1-1 miễn phí hoặc kiểm tra hỗ trợ ngay qua kênh Chat của sàn ạ.',
    MATERIAL_DURABILITY:
      'Về độ bền chất liệu và phụ liệu khóa kéo/nút bấm, Shop đã ghi nhận ý kiến để siết chặt tiêu chuẩn gia công cùng xưởng may và sẵn sàng gửi đổi sản phẩm mới nếu có lỗi vải.',
    FIT_SIZE:
      'Về kích cỡ và chiều dài che phủ, Shop xin rút kinh nghiệm để tư vấn bảng size chuẩn hơn khi ngồi xe máy hoặc mang balo. Shop luôn hỗ trợ đổi size linh hoạt qua tin nhắn Chat.',
    COMFORT_USABILITY:
      'Về độ tiện dụng và thoáng khí, Shop xin tiếp thu góp ý để cải tiến thiết kế mũ trùm, kính chắn nước và độ thông thoáng ở các lô sản xuất tiếp theo.',
    PRICE_VALUE:
      'Shop luôn nỗ lực tối ưu chất lượng tốt nhất trong tầm giá và rất mong có cơ hội phục vụ Quý khách chu đáo hơn ở những đơn hàng sau.',
    PACKAGING_SHIPPING:
      'Về khâu đóng gói và thời gian giao hàng, Shop xin chân thành xin lỗi vì trải nghiệm vận chuyển chưa trọn vẹn và đã làm việc lại với đơn vị vận chuyển để cải thiện tốc độ giao nhận.',
    CUSTOMER_SERVICE:
      'Shop chân thành xin lỗi vì sự chậm trễ hoặc thiếu sót trong quá trình tư vấn và cam kết phản hồi nhanh chóng nhất qua tin nhắn hỗ trợ.',
    ACCESSIBILITY_DESIGN:
      'Shop xin cảm ơn đóng góp quý báu về màu sắc và kiểu dáng để tiếp tục ra mắt thêm nhiều phiên bản tiện ích và thời trang hơn.',
    GENERAL:
      'Shop đã ghi nhận phản hồi và luôn sẵn sàng hỗ trợ Quý khách giải quyết mọi vấn đề phát sinh qua cổng Chat chính thức của sàn trong vòng 24h.',
  },
};

const OVERCLAIM_KEYWORDS = [
  'chống thấm 100%',
  'chống nước tuyệt đối',
  'không bao giờ thấm',
  'vĩnh viễn không rách',
  'bảo hành trọn đời',
];

const PROHIBITED_POLICY_KEYWORDS = [
  'tặng tiền đổi 5 sao',
  'hoàn tiền nếu đánh giá 5 sao',
  'xóa đánh giá 1 sao',
  'mua hộ đánh giá ảo',
  'chuyển khoản ngoài sàn',
  'zalo cá nhân',
];

const PHONE_RE = /(?:\+?84|0)(?:3|5|7|8|9)\d{8}\b/;
const EMAIL_RE = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/;
const LINK_RE = /(?:https?:\/\/|www\.)[^\s]+/i;
const MONEY_PROMISE_RE = /\b\d+(?:[.,]\d{3})*\s?(?:(?:k|đ|đồng|vnđ|vnd|nghìn|ngàn|triệu|percent)\b|%)/i;

let seedCachePromise = null;

function loadLocalOverlay() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch {
    // ignore storage errors
  }
  return {
    addedReviews: {},
    actionDecisions: {},
    repliesByReview: {},
    repliesById: {},
    nextReplyId: 9000,
    nextJobId: 500,
    jobs: {},
  };
}

function saveLocalOverlay(overlay) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overlay));
  } catch {
    // ignore quota errors
  }
}

export function clearStandaloneOverlay() {
  localStorage.removeItem(STORAGE_KEY);
}

async function getSeedData() {
  if (!seedCachePromise) {
    seedCachePromise = fetch('/standalone-seed.json')
      .then((res) => {
        if (!res.ok) throw new Error('Không thể nạp bộ dữ liệu mẫu nội bộ (/standalone-seed.json)');
        return res.json();
      })
      .catch((err) => {
        seedCachePromise = null;
        throw err;
      });
  }
  return seedCachePromise;
}

export function wilsonCiPct(successes, total, z = 1.96) {
  const n = Number(total || 0);
  const k = Math.max(0, Math.min(Number(successes || 0), n));
  if (n <= 0) return [0.0, 0.0];
  const p = k / n;
  const z2 = z * z;
  const denom = 1 + z2 / n;
  const center = (p + z2 / (2 * n)) / denom;
  const margin = (z * Math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom;
  const low = Math.max(0.0, Math.min(100.0, Number(((center - margin) * 100).toFixed(1))));
  const high = Math.max(0.0, Math.min(100.0, Number(((center + margin) * 100).toFixed(1))));
  return [low, high];
}

function normalCdf(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const prob =
    d *
    t *
    (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - prob : prob;
}

function levenshteinDistance(a = '', b = '') {
  const s1 = String(a);
  const s2 = String(b);
  const m = s1.length;
  const n = s2.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 0; i <= m; i += 1) dp[i][0] = i;
  for (let j = 0; j <= n; j += 1) dp[0][j] = j;
  for (let i = 1; i <= m; i += 1) {
    for (let j = 1; j <= n; j += 1) {
      const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[m][n];
}

export function checkReplyGuardrails(replyText, negativeAspects = []) {
  const violations = [];
  const textClean = String(replyText || '').trim();
  const textLower = textClean.toLowerCase();

  for (const kw of OVERCLAIM_KEYWORDS) {
    if (textLower.includes(kw.toLowerCase())) {
      violations.push(`G1 (Overclaim): Chứa cụm từ cam kết quá mức '${kw}'.`);
    }
  }
  for (const kw of PROHIBITED_POLICY_KEYWORDS) {
    if (textLower.includes(kw.toLowerCase())) {
      violations.push(`G2 (Platform Policy): Chứa điều khoản vi phạm chính sách sàn '${kw}'.`);
    }
  }
  if (PHONE_RE.test(textClean)) {
    violations.push('G3 (PII Leak): Chứa số điện thoại cá nhân trong phản hồi.');
  }
  if (EMAIL_RE.test(textClean)) {
    violations.push('G3 (PII Leak): Chứa địa chỉ email trong phản hồi.');
  }
  if (LINK_RE.test(textClean)) {
    violations.push('G3 (External Link): Chứa đường dẫn liên kết ngoài sàn.');
  }
  if (textClean.length < 40 || textClean.length > 600) {
    violations.push(
      `G4 (Length): Độ dài phản hồi (${textClean.length} ký tự) nằm ngoài khoảng cho phép 40-600 ký tự.`
    );
  }
  if (Array.isArray(negativeAspects) && negativeAspects.length > 0) {
    const unaddressed = [];
    for (const asp of negativeAspects) {
      const kws = ASPECT_KEYWORDS[asp] || [String(asp).toLowerCase()];
      if (!kws.some((k) => textLower.includes(k))) {
        unaddressed.push(asp);
      }
    }
    if (unaddressed.length > 0) {
      violations.push(
        `G5 (Aspect Coverage): Phản hồi chưa đề cập trực diện đến các vấn đề khách hàng phàn nàn: ${unaddressed.join(', ')}.`
      );
    }
  }
  if (MONEY_PROMISE_RE.test(textClean)) {
    violations.push('G6 (Unauthorized Money Promise): Tự ý hứa hẹn bồi thường tiền tệ cụ thể.');
  }

  return {
    passed: violations.length === 0,
    violations,
  };
}

function buildTemplateReply(negativeAspects = []) {
  const { greeting, closing, aspect_handlers: handlers } = REPLY_TEMPLATES;
  const bodySentences = [];
  const chosenAspects = [];
  const skippedAspects = [];

  if (Array.isArray(negativeAspects) && negativeAspects.length > 0) {
    for (const asp of negativeAspects) {
      if (handlers[asp] && !bodySentences.includes(handlers[asp])) {
        const cand = `${greeting} ${[...bodySentences, handlers[asp]].join(' ')} ${closing}`.trim();
        if (cand.length <= 580) {
          bodySentences.push(handlers[asp]);
          chosenAspects.push(asp);
        } else {
          skippedAspects.push(asp);
        }
      }
    }
  }

  if (skippedAspects.length > 0) {
    const phrases = skippedAspects.map((a) => ASPECT_SHORT_PHRASES[a] || a.toLowerCase());
    const extraNote = `Shop cũng ghi nhận góp ý về ${phrases.join(', ')} để cải thiện ngay ạ.`;
    const cand = `${greeting} ${bodySentences.join(' ')} ${extraNote} ${closing}`.trim();
    if (cand.length <= 600) {
      bodySentences.push(extraNote);
    } else if (bodySentences.length > 0) {
      bodySentences.pop();
      const allSkipped = [chosenAspects.pop(), ...skippedAspects].filter(Boolean);
      const allPhrases = allSkipped.map((a) => ASPECT_SHORT_PHRASES[a] || a.toLowerCase());
      bodySentences.push(`Shop cũng ghi nhận góp ý về ${allPhrases.join(', ')} để cải thiện ngay ạ.`);
    }
  }

  if (bodySentences.length === 0) {
    bodySentences.push(handlers.GENERAL);
  }

  let resText = `${greeting} ${bodySentences.join(' ')} ${closing}`.trim();
  if (resText.length > 600) {
    resText = `${resText.slice(0, 595).trimEnd()}...`;
  }
  return resText;
}

function scrubPiiText(raw = '') {
  return String(raw)
    .replace(PHONE_RE, '[SĐT_ĐÃ_ẨN]')
    .replace(EMAIL_RE, '[EMAIL_ĐÃ_ẨN]')
    .replace(LINK_RE, '[LIÊN_KẾT_ĐÃ_ẨN]')
    .trim();
}

function extractDeterministicOpinions(text = '', rating = 5) {
  const clean = String(text || '').trim();
  const lower = clean.toLowerCase();
  const hasNegCue = NEGATIVE_CUES.some((w) => lower.includes(w));
  const defaultPol = rating <= 2 ? 'negative' : rating === 3 ? (hasNegCue ? 'negative' : 'neutral') : hasNegCue ? 'negative' : 'positive';

  const opinions = [];
  for (const [aspect, kws] of Object.entries(ASPECT_KEYWORDS)) {
    if (aspect === 'GENERAL') continue;
    const matched = kws.find((kw) => lower.includes(kw));
    if (matched) {
      opinions.push({
        aspect,
        polarity: defaultPol,
        evidence: clean.slice(0, 120),
        evidence_ok: true,
      });
    }
  }

  if (opinions.length === 0) {
    opinions.push({
      aspect: 'GENERAL',
      polarity: rating >= 4 && !hasNegCue ? 'positive' : rating <= 2 || hasNegCue ? 'negative' : 'neutral',
      evidence: clean.slice(0, 120),
      evidence_ok: true,
    });
  }
  return opinions;
}

async function getScenarioData(scenarioTag = 'real_shop') {
  const seed = await getSeedData();
  const base = seed.scenarios?.[scenarioTag] || seed.scenarios?.real_shop;
  const overlay = loadLocalOverlay();
  const extraReviews = overlay.addedReviews?.[scenarioTag] || [];
  const allReviews = [...extraReviews, ...(base?.reviews || [])];

  const reviewsWithReplies = allReviews.map((rev) => {
    const key = `${scenarioTag}:${rev.review_id}`;
    const list = overlay.repliesByReview?.[key] || [];
    if (list.length > 0) {
      const latest = list[list.length - 1];
      return {
        ...rev,
        reply_status: latest.status,
        latest_reply: latest,
      };
    }
    return rev;
  });

  const actions = (base?.actions || []).map((act) => {
    const dec = overlay.actionDecisions?.[act.id];
    if (!dec) return act;
    return {
      ...act,
      status: dec.status,
      what_to_do: dec.edited_content || act.what_to_do,
    };
  });

  return {
    seed,
    base,
    overlay,
    extraReviews,
    reviews: reviewsWithReplies,
    actions,
    insights: base?.insights || [],
    alerts: base?.alerts || [],
  };
}

function recomputeOverviewWithAddedReviews(baseOverview, allReviews, minN = 3) {
  const totalReviews = allReviews.length;
  if (totalReviews === 0) return baseOverview;

  let ratingSum = 0;
  let posReviews = 0;
  let negReviews = 0;
  let shopeeCount = 0;
  let tiktokCount = 0;
  let highRatingTotal = 0;
  const hiddenItems = [];
  const aspectBuckets = {};

  for (const r of allReviews) {
    const rating = Number(r.rating || 5);
    ratingSum += rating;
    if (r.overall_sentiment === 'positive') posReviews += 1;
    if (r.overall_sentiment === 'negative') negReviews += 1;
    if (r.platform === 'shopee') shopeeCount += 1;
    if (r.platform === 'tiktok') tiktokCount += 1;
    if (rating >= 4) highRatingTotal += 1;

    for (const op of r.opinions || []) {
      const asp = op.aspect;
      if (!aspectBuckets[asp]) {
        aspectBuckets[asp] = { total: 0, pos: 0, neg: 0, neu: 0 };
      }
      aspectBuckets[asp].total += 1;
      if (op.polarity === 'positive') aspectBuckets[asp].pos += 1;
      else if (op.polarity === 'negative') {
        aspectBuckets[asp].neg += 1;
        if (rating >= 4) {
          hiddenItems.push({
            review_id: r.review_id,
            platform: r.platform,
            rating,
            aspect: asp,
            evidence: op.evidence,
            text_raw: r.text_raw,
          });
        }
      } else {
        aspectBuckets[asp].neu += 1;
      }
    }
  }

  const avgRating = Number((ratingSum / totalReviews).toFixed(2));
  const negRatePct = Number(((negReviews / totalReviews) * 100).toFixed(1));
  const negCi95 = wilsonCiPct(negReviews, totalReviews);

  const aspectStats = Object.entries(aspectBuckets)
    .filter(([, b]) => b.total >= minN)
    .map(([aspect, b]) => {
      const [ciLow, ciHigh] = wilsonCiPct(b.neg, b.total);
      return {
        aspect,
        total_mentions: b.total,
        pos_count: b.pos,
        neg_count: b.neg,
        neu_count: b.neu,
        pos_pct: Number(((b.pos / b.total) * 100).toFixed(1)),
        neg_pct: Number(((b.neg / b.total) * 100).toFixed(1)),
        wilson_ci_low: ciLow,
        wilson_ci_high: ciHigh,
        confidence: b.total >= 30 ? 'high' : b.total >= 10 ? 'medium' : 'low',
      };
    })
    .sort((a, b) => b.neg_pct - a.neg_pct || b.total_mentions - a.total_mentions);

  const hiddenCounts = {};
  const hiddenReviewIds = new Set();
  for (const h of hiddenItems) {
    hiddenReviewIds.add(h.review_id);
    hiddenCounts[h.aspect] = (hiddenCounts[h.aspect] || 0) + 1;
  }
  const topHiddenAspects = Object.entries(hiddenCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([aspect, count]) => ({ aspect, count }));

  return {
    ...baseOverview,
    total_reviews: totalReviews,
    avg_rating: avgRating,
    positive_reviews: posReviews,
    negative_reviews: negReviews,
    negative_rate_pct: negRatePct,
    negative_ci_95: negCi95,
    platform_counts: {
      shopee: shopeeCount,
      tiktok: tiktokCount,
    },
    aspect_stats: aspectStats,
    hidden_complaints: {
      hidden_count: hiddenReviewIds.size,
      high_rating_total: highRatingTotal,
      top_hidden_aspects: topHiddenAspects,
      items: hiddenItems,
    },
  };
}

function getBucketKey(dateStr, period = 'month') {
  if (!dateStr) return '2025-11';
  const clean = String(dateStr).slice(0, 10);
  if (period === 'week') {
    const dt = new Date(clean);
    if (Number.isNaN(dt.getTime())) return clean.slice(0, 7);
    const oneJan = new Date(dt.getFullYear(), 0, 1);
    const days = Math.floor((dt - oneJan) / 86400000);
    const week = Math.max(1, Math.ceil((days + oneJan.getDay() + 1) / 7));
    return `${dt.getFullYear()}-W${String(week).padStart(2, '0')}`;
  }
  return clean.slice(0, 7);
}

export const standaloneEngine = {
  async getHealth() {
    const seed = await getSeedData();
    const overlay = loadLocalOverlay();
    const addedCount = Object.values(overlay.addedReviews || {}).reduce(
      (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
      0
    );
    return {
      status: 'healthy',
      standalone_mode: true,
      database_backend: 'standalone_local',
      database_status: 'connected',
      total_reviews_in_db: (seed.total_reviews_in_db || 0) + addedCount,
      demo_cache_mode: true,
      auth_enabled: false,
      endpoints_count: 15,
      extended_endpoints_count: 18,
    };
  },

  async getOverviewStats(scenarioTag = 'real_shop', minN = 3) {
    const { base, extraReviews, reviews } = await getScenarioData(scenarioTag);
    if (extraReviews.length === 0 && base?.overview) {
      return base.overview;
    }
    return recomputeOverviewWithAddedReviews(base?.overview || {}, reviews, minN);
  },

  async getInsights(scenarioTag = 'real_shop', kind = '') {
    const { insights } = await getScenarioData(scenarioTag);
    const filtered = kind
      ? insights.filter((i) => !i.is_archived && i.kind === kind)
      : insights.filter((i) => !i.is_archived);
    return {
      scenario_tag: scenarioTag,
      count: filtered.length,
      insights: filtered,
    };
  },

  async getAlerts(scenarioTag = 'real_shop') {
    const { alerts } = await getScenarioData(scenarioTag);
    return {
      scenario_tag: scenarioTag,
      alerts_count: alerts.length,
      alerts,
    };
  },

  async getTrends(scenarioTag = 'real_shop', period = 'month', aspect = '', minN = 2) {
    const { base, extraReviews, reviews } = await getScenarioData(scenarioTag);
    if (!aspect && extraReviews.length === 0 && base?.trends?.[period]) {
      return {
        scenario_tag: scenarioTag,
        aspect: 'ALL',
        period_type: period,
        buckets_count: base.trends[period].length,
        trends: base.trends[period],
      };
    }

    const buckets = {};
    for (const r of reviews) {
      const bKey = getBucketKey(r.created_at, period);
      const ops = aspect
        ? (r.opinions || []).filter((o) => o.aspect === aspect)
        : r.opinions || [];
      for (const op of ops) {
        if (!buckets[bKey]) {
          buckets[bKey] = { total: 0, pos: 0, neg: 0, neu: 0 };
        }
        buckets[bKey].total += 1;
        if (op.polarity === 'positive') buckets[bKey].pos += 1;
        else if (op.polarity === 'negative') buckets[bKey].neg += 1;
        else buckets[bKey].neu += 1;
      }
    }

    const trends = Object.entries(buckets)
      .filter(([, b]) => b.total >= minN)
      .sort(([k1], [k2]) => k1.localeCompare(k2))
      .map(([bKey, b]) => {
        const [ciLow, ciHigh] = wilsonCiPct(b.neg, b.total);
        return {
          period: bKey,
          aspect: aspect || 'ALL',
          total: b.total,
          neg_count: b.neg,
          pos_count: b.pos,
          neu_count: b.neu,
          neg_pct: Number(((b.neg / b.total) * 100).toFixed(1)),
          pos_pct: Number(((b.pos / b.total) * 100).toFixed(1)),
          wilson_ci_low: ciLow,
          wilson_ci_high: ciHigh,
          confidence: b.total >= 30 ? 'high' : b.total >= 10 ? 'medium' : 'low',
        };
      });

    return {
      scenario_tag: scenarioTag,
      aspect: aspect || 'ALL',
      period_type: period,
      buckets_count: trends.length,
      trends,
    };
  },

  async getActions(
    scenarioTag = 'real_shop',
    isMarketing = null,
    status = '',
    includeArchived = false
  ) {
    const { actions } = await getScenarioData(scenarioTag);
    const filtered = actions.filter((a) => {
      if (!includeArchived && a.is_archived) return false;
      if (isMarketing !== null && isMarketing !== undefined && isMarketing !== '') {
        if (Boolean(a.is_marketing) !== Boolean(isMarketing)) return false;
      }
      if (status) {
        if (String(a.status || 'PENDING').toUpperCase() !== status.trim().toUpperCase()) {
          return false;
        }
      }
      return true;
    });
    return {
      scenario_tag: scenarioTag,
      count: filtered.length,
      actions: filtered,
    };
  },

  async generateActions(scenarioTag = 'real_shop') {
    const { insights, actions } = await getScenarioData(scenarioTag);
    const activeActions = actions.filter((a) => !a.is_archived);
    return {
      scenario_tag: scenarioTag,
      insights_count: insights.filter((i) => !i.is_archived).length,
      actions_count: activeActions.length,
      final_critic_score: 5.0,
      iterations: 1,
      repaired_count: 0,
      planner_mode: 'standalone_deterministic',
      status: 'completed',
    };
  },

  async submitActionDecision(actionId, payload) {
    const reviewer = localStorage.getItem('ecomreview_reviewer') || 'chu_shop_aomua';
    const decision = String(payload?.decision || 'APPROVED').toUpperCase();
    const seed = await getSeedData();
    let targetAction = null;
    for (const sc of Object.values(seed.scenarios || {})) {
      const found = (sc.actions || []).find((a) => Number(a.id) === Number(actionId));
      if (found) {
        targetAction = found;
        break;
      }
    }
    if (!targetAction) {
      throw new Error(`Không tìm thấy đề xuất hành động #${actionId}`);
    }

    const editedContent = String(payload?.edited_content || '').trim();
    const editDistance =
      decision === 'EDITED' && editedContent
        ? levenshteinDistance(targetAction.what_to_do || '', editedContent)
        : 0;

    const overlay = loadLocalOverlay();
    overlay.actionDecisions[actionId] = {
      action_id: Number(actionId),
      status: decision,
      decision,
      note: payload?.note || '',
      edited_content: editedContent,
      reason_category: payload?.reason_category || '',
      edit_distance: editDistance,
      decided_by: reviewer,
      decided_at: new Date().toISOString(),
    };
    saveLocalOverlay(overlay);
    return overlay.actionDecisions[actionId];
  },

  async getActionImpact(actionId, windowDays = 30, since = '', minN = 2) {
    const seed = await getSeedData();
    let targetAction = null;
    let scenarioTag = 'real_shop';
    for (const [scKey, sc] of Object.entries(seed.scenarios || {})) {
      const found = (sc.actions || []).find((a) => Number(a.id) === Number(actionId));
      if (found) {
        targetAction = found;
        scenarioTag = scKey;
        break;
      }
    }
    if (!targetAction) {
      throw new Error(`Action ${actionId} not found.`);
    }

    const { reviews, insights } = await getScenarioData(scenarioTag);
    const linkedAspects = insights
      .filter((i) => (targetAction.insight_ids || []).includes(i.insight_id) && i.aspect)
      .map((i) => i.aspect);
    const targetAspects = [...new Set(linkedAspects)];

    const milestoneStr =
      since ||
      (targetAction.created_at
        ? String(targetAction.created_at).slice(0, 10)
        : '2025-10-15');
    const milestoneMs = new Date(milestoneStr).getTime();
    const windowMs = Number(windowDays || 30) * 86400000;

    let preTotal = 0;
    let preNeg = 0;
    let postTotal = 0;
    let postNeg = 0;

    for (const r of reviews) {
      const rMs = new Date(String(r.created_at || '2025-10-01').slice(0, 10)).getTime();
      if (Number.isNaN(rMs)) continue;
      const ops =
        targetAspects.length > 0
          ? (r.opinions || []).filter((o) => targetAspects.includes(o.aspect))
          : r.opinions || [];
      for (const op of ops) {
        if (rMs >= milestoneMs - windowMs && rMs < milestoneMs) {
          preTotal += 1;
          if (op.polarity === 'negative') preNeg += 1;
        } else if (rMs >= milestoneMs && rMs <= milestoneMs + windowMs) {
          postTotal += 1;
          if (op.polarity === 'negative') postNeg += 1;
        }
      }
    }

    const prePct = preTotal > 0 ? Number(((preNeg / preTotal) * 100).toFixed(1)) : 0.0;
    const postPct = postTotal > 0 ? Number(((postNeg / postTotal) * 100).toFixed(1)) : 0.0;
    const preCi = wilsonCiPct(preNeg, preTotal);
    const postCi = wilsonCiPct(postNeg, postTotal);

    if (preTotal < minN || postTotal < minN) {
      return {
        action_id: Number(actionId),
        scenario_tag: scenarioTag,
        target_aspects: targetAspects,
        milestone_date: milestoneStr,
        window_days: Number(windowDays),
        pre_window: { total: preTotal, neg_count: preNeg, neg_pct: prePct, ci_95: preCi },
        post_window: { total: postTotal, neg_count: postNeg, neg_pct: postPct, ci_95: postCi },
        delta_pp: Number((postPct - prePct).toFixed(1)),
        z_score: 0.0,
        p_value: 1.0,
        status: 'insufficient_data',
        disclaimer:
          'Quan sát đối chứng trước/sau can thiệp; không mang tính quy kết nhân quả tuyệt đối.',
      };
    }

    const p1 = preNeg / preTotal;
    const p2 = postNeg / postTotal;
    const pPool = (preNeg + postNeg) / (preTotal + postTotal);
    const se = Math.sqrt(pPool * (1 - pPool) * (1 / preTotal + 1 / postTotal));
    const zScore = se > 0 ? Number(((p2 - p1) / se).toFixed(4)) : 0.0;
    const pValue = Number((2 * (1 - normalCdf(Math.abs(zScore)))).toFixed(4));
    const deltaPp = Number((postPct - prePct).toFixed(1));

    let status = 'no_significant_change';
    if (pValue < 0.05) {
      status = deltaPp < 0 ? 'improved' : 'worsened';
    }

    return {
      action_id: Number(actionId),
      scenario_tag: scenarioTag,
      target_aspects: targetAspects,
      milestone_date: milestoneStr,
      window_days: Number(windowDays),
      pre_window: { total: preTotal, neg_count: preNeg, neg_pct: prePct, ci_95: preCi },
      post_window: { total: postTotal, neg_count: postNeg, neg_pct: postPct, ci_95: postCi },
      delta_pp: deltaPp,
      z_score: zScore,
      p_value: pValue,
      status,
      disclaimer:
        'Quan sát đối chứng trước/sau can thiệp; không mang tính quy kết nhân quả tuyệt đối.',
    };
  },

  async getReviews({
    scenarioTag = 'real_shop',
    platform = '',
    aspect = '',
    polarity = '',
    reviewIds = '',
    limit = 50,
    offset = 0,
  } = {}) {
    const { reviews } = await getScenarioData(scenarioTag);
    const idList = reviewIds
      ? reviewIds
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

    const filtered = reviews.filter((r) => {
      if (idList.length > 0 && !idList.includes(String(r.review_id))) return false;
      if (platform && r.platform !== platform) return false;
      if (aspect) {
        const hasAspect = (r.opinions || []).some(
          (op) => op.aspect === aspect && (!polarity || op.polarity === polarity)
        );
        if (!hasAspect) return false;
      } else if (polarity) {
        if (String(r.overall_sentiment || '').toLowerCase() !== polarity.toLowerCase()) {
          return false;
        }
      }
      return true;
    });

    const sliced = filtered.slice(Number(offset), Number(offset) + Number(limit));
    return {
      scenario_tag: scenarioTag,
      count: sliced.length,
      total_count: filtered.length,
      reviews: sliced,
    };
  },

  async uploadReviews(payload) {
    const scenarioTag = payload?.scenario_tag || 'real_shop';
    const items = Array.isArray(payload?.reviews) ? payload.reviews : [];
    const overlay = loadLocalOverlay();
    if (!overlay.addedReviews[scenarioTag]) {
      overlay.addedReviews[scenarioTag] = [];
    }

    let inserted = 0;
    for (const item of items) {
      const cleanText = scrubPiiText(item.text || item.text_raw || '');
      if (!cleanText) continue;
      const rating = Number(item.rating || 5);
      const opinions =
        Array.isArray(item.opinions) && item.opinions.length > 0
          ? item.opinions
          : extractDeterministicOpinions(cleanText, rating);
      const hasNeg = opinions.some((o) => o.polarity === 'negative');
      const overallSentiment =
        item.overall_sentiment ||
        (hasNeg || rating <= 2 ? 'negative' : rating >= 4 ? 'positive' : 'neutral');

      overlay.addedReviews[scenarioTag].unshift({
        review_id: item.review_id || `LOCAL_${Date.now()}_${inserted + 1}`,
        platform: item.platform || 'shopee',
        rating,
        text_raw: cleanText,
        created_at: item.created_at || new Date().toISOString().slice(0, 10),
        overall_sentiment: overallSentiment,
        reply_status: 'NONE',
        latest_reply: null,
        opinions,
      });
      inserted += 1;
    }

    const jobId = ++overlay.nextJobId;
    saveLocalOverlay(overlay);
    return {
      job_id: jobId,
      scenario_tag: scenarioTag,
      inserted_count: inserted,
      analyzer_method: 'b1_rule_standalone',
      status: 'completed',
    };
  },

  async uploadReviewFile(formData) {
    const file = formData.get('file');
    const scenarioTag = formData.get('scenario_tag') || 'real_shop';
    const defaultPlatform = formData.get('platform') || 'shopee';

    if (!file) {
      throw new Error('Vui lòng chọn tệp đánh giá (.csv) để tải lên.');
    }
    const name = String(file.name || '').toLowerCase();
    if (!name.endsWith('.csv') && !name.endsWith('.txt')) {
      throw new Error(
        'Ở Chế độ Độc lập (không bật Backend Python), trình duyệt hỗ trợ nạp trực tiếp tệp .CSV. Để nạp tệp .XLSX nhị phân, vui lòng bật Backend hoặc lưu tệp sang định dạng CSV UTF-8.'
      );
    }

    const textContent = await file.text();
    const lines = textContent
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);

    if (lines.length < 2) {
      throw new Error('Tệp CSV không có dữ liệu hợp lệ.');
    }

    const headers = lines[0].split(',').map((h) => h.replace(/^"|"$/g, '').trim().toLowerCase());
    const textIdx = headers.findIndex((h) => ['text', 'text_raw', 'comment', 'review', 'noi_dung'].includes(h));
    const ratingIdx = headers.findIndex((h) => ['rating', 'star', 'stars', 'so_sao'].includes(h));
    const platformIdx = headers.findIndex((h) => ['platform', 'san'].includes(h));
    const idIdx = headers.findIndex((h) => ['review_id', 'id'].includes(h));

    const validReviews = [];
    const skippedRows = [];

    for (let i = 1; i < lines.length; i += 1) {
      const cols = lines[i].split(',').map((c) => c.replace(/^"|"$/g, '').trim());
      const rawText = textIdx >= 0 ? cols[textIdx] : cols[cols.length - 1];
      if (!rawText || rawText.length < 2) {
        skippedRows.push({ row: i + 1, reason: 'Nội dung trống' });
        continue;
      }
      const ratingVal = ratingIdx >= 0 ? Number(cols[ratingIdx]) : 5;
      const rating = Number.isFinite(ratingVal) ? Math.min(5, Math.max(1, Math.round(ratingVal))) : 5;
      const platform =
        platformIdx >= 0 && ['shopee', 'tiktok'].includes(cols[platformIdx]?.toLowerCase())
          ? cols[platformIdx].toLowerCase()
          : defaultPlatform;
      const reviewId = idIdx >= 0 && cols[idIdx] ? cols[idIdx] : `CSV_${Date.now()}_${i}`;

      validReviews.push({
        review_id: reviewId,
        platform,
        rating,
        text: rawText,
      });
    }

    const res = await this.uploadReviews({
      scenario_tag: scenarioTag,
      reviews: validReviews,
    });

    return {
      ...res,
      skipped_count: skippedRows.length,
      skipped_rows: skippedRows.slice(0, 20),
    };
  },

  async runAnalysis(payload) {
    const scenarioTag = payload?.scenario_tag || 'real_shop';
    const { insights } = await getScenarioData(scenarioTag);
    const overlay = loadLocalOverlay();
    const jobId = ++overlay.nextJobId;
    const count = insights.filter((i) => !i.is_archived).length;
    overlay.jobs[jobId] = {
      job_id: jobId,
      job_type: 'analyze_run',
      status: 'completed',
      details: {
        scenario_tag: scenarioTag,
        insights_generated: count,
      },
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    };
    saveLocalOverlay(overlay);

    if (payload?.async_mode) {
      return {
        job_id: jobId,
        scenario_tag: scenarioTag,
        status: 'running',
        message: 'Analysis started in standalone mode.',
      };
    }

    return {
      job_id: jobId,
      scenario_tag: scenarioTag,
      insights_generated: count,
      status: 'completed',
    };
  },

  async getJobStatus(jobId) {
    const overlay = loadLocalOverlay();
    return (
      overlay.jobs?.[jobId] || {
        job_id: Number(jobId),
        job_type: 'analyze_run',
        status: 'completed',
        details: { insights_generated: 5 },
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
      }
    );
  },

  async createReplyDraft(reviewId, scenarioTag = 'real_shop', mode = 'template') {
    const { reviews, overlay } = await getScenarioData(scenarioTag);
    const target = reviews.find((r) => String(r.review_id) === String(reviewId));
    if (!target) {
      throw new Error(`Không tìm thấy đánh giá ${reviewId}`);
    }

    const negAspects = [
      ...new Set(
        (target.opinions || [])
          .filter((o) => o.polarity === 'negative')
          .map((o) => o.aspect)
      ),
    ];

    const replyText = buildTemplateReply(negAspects);
    const guardrailReport = checkReplyGuardrails(replyText, negAspects);
    const reviewer = localStorage.getItem('ecomreview_reviewer') || 'chu_shop_aomua';
    const replyId = ++overlay.nextReplyId;
    const nowIso = new Date().toISOString();

    const record = {
      reply_id: replyId,
      review_id: String(reviewId),
      scenario_tag: scenarioTag,
      platform: target.platform,
      rating: target.rating,
      negative_aspects: negAspects,
      reply_text: replyText,
      addressed_aspects: negAspects,
      mode_used: mode === 'llm' ? 'template_standalone' : 'template',
      guardrail_report: guardrailReport,
      guardrail_passed: guardrailReport.passed,
      violations: guardrailReport.violations,
      status: 'DRAFT',
      created_by: reviewer,
      created_at: nowIso,
      sent_at: null,
    };

    const key = `${scenarioTag}:${reviewId}`;
    if (!overlay.repliesByReview[key]) {
      overlay.repliesByReview[key] = [];
    }
    overlay.repliesByReview[key].push(record);
    overlay.repliesById[replyId] = { ...record, reviewKey: key };
    saveLocalOverlay(overlay);

    return record;
  },

  async getReviewReplies(reviewId, scenarioTag = 'real_shop') {
    const overlay = loadLocalOverlay();
    const key = `${scenarioTag}:${reviewId}`;
    const list = (overlay.repliesByReview?.[key] || []).slice().reverse();
    return {
      review_id: reviewId,
      scenario_tag: scenarioTag,
      count: list.length,
      replies: list,
    };
  },

  async updateReplyStatus(replyId, status, replyText = null) {
    const targetStatus = String(status || '').trim().toUpperCase();
    const overlay = loadLocalOverlay();
    const existing = overlay.repliesById?.[replyId];
    if (!existing) {
      throw new Error(`Không tìm thấy bản nháp phản hồi #${replyId}`);
    }

    const finalText =
      replyText !== null && String(replyText).trim()
        ? String(replyText).trim()
        : existing.reply_text;

    const report = checkReplyGuardrails(finalText, existing.negative_aspects || []);
    if (!report.passed && (targetStatus === 'APPROVED' || targetStatus === 'SENT')) {
      throw new Error(`Nội dung phản hồi vi phạm quy tắc an toàn G1-G6: ${report.violations.join('; ')}`);
    }

    const updated = {
      ...existing,
      reply_text: finalText,
      status: targetStatus,
      guardrail_passed: report.passed,
      violations: report.violations,
      guardrail_report: report,
      sent_at: targetStatus === 'SENT' ? new Date().toISOString() : existing.sent_at,
    };

    overlay.repliesById[replyId] = updated;
    const list = overlay.repliesByReview?.[existing.reviewKey] || [];
    overlay.repliesByReview[existing.reviewKey] = list.map((item) =>
      Number(item.reply_id) === Number(replyId) ? updated : item
    );
    saveLocalOverlay(overlay);
    return updated;
  },

  async downloadReport(scenarioTag = 'real_shop', format = 'html') {
    const overview = await this.getOverviewStats(scenarioTag, 3);
    const { insights, actions } = await getScenarioData(scenarioTag);

    if (format === 'xlsx') {
      // Export UTF-8 CSV with BOM so Microsoft Excel opens Vietnamese characters cleanly in standalone mode
      const rows = [
        ['BÁO CÁO ĐIỀU HÀNH ECOMREVIEW AI (CHẾ ĐỘ ĐỘC LẬP)', scenarioTag],
        ['Tổng đánh giá', overview.total_reviews],
        ['Điểm sao trung bình', overview.avg_rating],
        ['Tỷ lệ phàn nàn (%)', `${overview.negative_rate_pct}%`],
        [],
        ['KHÍA CẠNH', 'TỔNG LƯỢT NHẮC', 'KHEN (%)', 'PHÀN NÀN (%)', 'WILSON 95% CI'],
        ...(overview.aspect_stats || []).map((s) => [
          getAspectLabel(s.aspect),
          s.total_mentions,
          `${s.pos_pct}%`,
          `${s.neg_pct}%`,
          `${s.wilson_ci_low}% - ${s.wilson_ci_high}%`,
        ]),
        [],
        ['ĐỀ XUẤT HÀNH ĐỘNG', 'NHÓM', 'TRẠNG THÁI', 'VIỆC CẦN LÀM', 'KPI MỤC TIÊU'],
        ...actions
          .filter((a) => !a.is_archived)
          .map((a) => [
            a.title,
            a.is_marketing ? 'Marketing' : 'Vận hành & Sản phẩm',
            a.status,
            a.what_to_do,
            a.success_metric,
          ]),
      ];

      const csvContent =
        '\uFEFF' +
        rows
          .map((r) =>
            r.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')
          )
          .join('\r\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `EcomReview_Report_${scenarioTag}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
      return;
    }

    const html = `<!doctype html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <title>Báo cáo Điều hành EcomReview AI — ${scenarioTag}</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; color: #0f172a; max-width: 960px; margin: 32px auto; padding: 0 20px; line-height: 1.5; }
    h1 { color: #312e81; margin-bottom: 4px; }
    h2 { color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 28px; }
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
    .kpi { border: 1px solid #cbd5e1; border-radius: 10px; padding: 12px; background: #f8fafc; }
    .kpi-val { font-size: 22px; font-weight: 700; color: #4338ca; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; }
    th { background: #f1f5f9; }
    @media print { .no-print { display: none; } }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom:16px;">
    <button onclick="window.print()" style="padding:8px 16px;background:#4f46e5;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;">In báo cáo / Lưu PDF</button>
  </div>
  <h1>Báo Cáo Điều Hành EcomReview AI (${scenarioTag})</h1>
  <p style="color:#64748b;margin-top:0;">Chế độ Độc lập • Dữ liệu xác thực 100% (Wilson 95% CI)</p>
  <div class="kpi-grid">
    <div class="kpi"><div>Tổng đánh giá</div><div class="kpi-val">${overview.total_reviews}</div></div>
    <div class="kpi"><div>Điểm sao TB</div><div class="kpi-val">${overview.avg_rating} / 5.0</div></div>
    <div class="kpi"><div>Tỷ lệ phàn nàn</div><div class="kpi-val">${overview.negative_rate_pct}%</div></div>
    <div class="kpi"><div>Phàn nàn ẩn (4-5★)</div><div class="kpi-val">${overview.hidden_complaints?.hidden_count ?? 0}</div></div>
  </div>
  <h2>1. Thống kê 8 Khía cạnh ABSA</h2>
  <table>
    <thead><tr><th>Khía cạnh</th><th>Tổng lượt nhắc</th><th>Khen (%)</th><th>Phàn nàn (%)</th><th>Wilson 95% CI</th></tr></thead>
    <tbody>
      ${(overview.aspect_stats || [])
        .map(
          (s) =>
            `<tr><td>${getAspectLabel(s.aspect)}</td><td>${s.total_mentions}</td><td>${s.pos_pct}%</td><td>${s.neg_pct}%</td><td>${s.wilson_ci_low}% – ${s.wilson_ci_high}%</td></tr>`
        )
        .join('')}
    </tbody>
  </table>
  <h2>2. Phát hiện Chính (${insights.filter((i) => !i.is_archived).length})</h2>
  <ul>
    ${insights
      .filter((i) => !i.is_archived)
      .map((i) => `<li><strong>[${i.kind}]</strong> ${i.statement}</li>`)
      .join('')}
  </ul>
  <h2>3. Kế hoạch Hành động (${actions.filter((a) => !a.is_archived).length})</h2>
  <table>
    <thead><tr><th>Hạng mục</th><th>Nhóm</th><th>Trạng thái</th><th>Việc cần làm</th><th>KPI mục tiêu</th></tr></thead>
    <tbody>
      ${actions
        .filter((a) => !a.is_archived)
        .map(
          (a) =>
            `<tr><td><strong>${a.title}</strong></td><td>${a.is_marketing ? 'Marketing' : 'Vận hành'}</td><td>${a.status}</td><td>${a.what_to_do}</td><td>${a.success_metric}</td></tr>`
        )
        .join('')}
    </tbody>
  </table>
</body>
</html>`;

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const blobUrl = window.URL.createObjectURL(blob);
    window.open(blobUrl, '_blank', 'noopener,noreferrer');
    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
  },
};

// CreBy: MenBoyBMN
