import { standaloneEngine, clearStandaloneOverlay } from './standaloneEngine';

const DEFAULT_ENV_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const IS_PRODUCTION_APP =
  (import.meta.env.VITE_APP_MODE || '').trim().toLowerCase() === 'production';
const DEFAULT_ENV_MODE = IS_PRODUCTION_APP
  ? 'remote'
  : import.meta.env.VITE_CONNECTION_MODE || 'auto';

let runtimeStandbyActive = false;
let inFlightRefreshPromise = null;

async function tryRefreshSession(baseUrl) {
  if (!inFlightRefreshPromise) {
    inFlightRefreshPromise = fetch(`${baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        inFlightRefreshPromise = null;
      });
  }
  return inFlightRefreshPromise;
}

export function getConnectionConfig() {
  if (IS_PRODUCTION_APP) {
    return { mode: 'remote', baseUrl: DEFAULT_ENV_BASE };
  }
  const mode = localStorage.getItem('ecomreview_connection_mode') || DEFAULT_ENV_MODE;
  const baseUrl = (
    localStorage.getItem('ecomreview_api_base_url') ?? DEFAULT_ENV_BASE
  ).replace(/\/+$/, '');
  return {
    mode: ['auto', 'standalone', 'remote'].includes(mode) ? mode : 'auto',
    baseUrl,
  };
}

export function setConnectionConfig({ mode, baseUrl }) {
  if (IS_PRODUCTION_APP) {
    runtimeStandbyActive = false;
    return;
  }
  if (mode) {
    localStorage.setItem('ecomreview_connection_mode', mode);
  }
  if (baseUrl !== undefined) {
    localStorage.setItem('ecomreview_api_base_url', String(baseUrl).trim().replace(/\/+$/, ''));
  }
  runtimeStandbyActive = mode === 'standalone';
}

export function resetStandaloneData() {
  clearStandaloneOverlay();
}

function buildHeaders(extra = {}, includeJsonContentType = false) {
  const headers = { ...extra };
  if (!IS_PRODUCTION_APP) {
    const apiKey = localStorage.getItem('ecomreview_api_key') || '';
    const reviewer = localStorage.getItem('ecomreview_reviewer') || 'chu_shop_aomua';
    headers['X-Reviewer'] = reviewer;
    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }
  }
  if (includeJsonContentType && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

async function rawFetchJson(path, options = {}) {
  const { baseUrl } = getConnectionConfig();
  const url = `${baseUrl}${path}`;
  const hasJsonBody = options.body !== undefined && !(options.body instanceof FormData);

  let response;
  try {
    response = await fetch(url, {
      credentials: 'include',
      ...options,
      headers: buildHeaders(options.headers, hasJsonBody),
    });
  } catch (networkErr) {
    const err = new Error(networkErr.message || 'Network error');
    err.isBackendUnreachable = true;
    throw err;
  }

  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');

  if (!response.ok) {
    if (
      response.status === 401 &&
      !options._retried &&
      !path.startsWith('/api/v1/auth/login') &&
      !path.startsWith('/api/v1/auth/refresh') &&
      !path.startsWith('/api/v1/auth/logout')
    ) {
      const refreshed = await tryRefreshSession(baseUrl);
      if (refreshed) {
        return rawFetchJson(path, { ...options, _retried: true });
      }
      window.dispatchEvent(new CustomEvent('ecomreview:unauthorized'));
    } else if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('ecomreview:unauthorized'));
    }
    // When Vite proxy cannot reach 127.0.0.1:8000 or static host has no /api route,
    // it returns non-JSON 500/502/503/504 or 404 HTML/text.
    if (!isJson && (response.status >= 500 || response.status === 404)) {
      const err = new Error(`Backend unreachable (HTTP ${response.status})`);
      err.isBackendUnreachable = true;
      throw err;
    }

    let errorDetail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      const detail = errJson.detail;
      if (Array.isArray(detail)) {
        errorDetail = detail
          .map((d) =>
            typeof d === 'object' && d !== null ? d.msg || JSON.stringify(d) : String(d)
          )
          .join('; ');
      } else if (typeof detail === 'object' && detail !== null) {
        errorDetail = JSON.stringify(detail);
      } else {
        errorDetail = detail || errJson.message || errorDetail;
      }
    } catch {
      // ignore json parse error
    }
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  if (!isJson) {
    const err = new Error('Unexpected non-JSON response from API');
    err.isBackendUnreachable = true;
    throw err;
  }

  return response.json();
}

async function callWithPolicy(remoteFn, standaloneFn, forceProbe = false) {
  const { mode } = getConnectionConfig();
  if (IS_PRODUCTION_APP || mode === 'remote') {
    runtimeStandbyActive = false;
    return remoteFn();
  }
  if (mode === 'standalone') {
    runtimeStandbyActive = true;
    return standaloneFn();
  }
  if (mode === 'auto' && runtimeStandbyActive && !forceProbe) {
    return standaloneFn();
  }
  try {
    const res = await remoteFn();
    runtimeStandbyActive = false;
    return res;
  } catch (err) {
    if (mode === 'auto' && err.isBackendUnreachable) {
      runtimeStandbyActive = true;
      return standaloneFn();
    }
    throw err;
  }
}

export const api = {
  // Pilot Auth & Shop Management
  login: (email, password) =>
    rawFetchJson('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    rawFetchJson('/api/v1/auth/logout', {
      method: 'POST',
    }),

  refreshSession: () =>
    rawFetchJson('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  changePassword: (currentPassword, newPassword) =>
    rawFetchJson('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    }),

  getMe: () => rawFetchJson('/api/v1/auth/me'),

  getShops: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/shops'),
      () => ({ count: 0, shops: [] })
    ),

  getIndustries: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/industries'),
      () => ({ industries: [{ industry: 'raincoat', display_name: 'Áo mưa & Đồ đi mưa' }] })
    ),

  updateShopAlerts: (slug, payload) =>
    rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/alerts`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  updateShopProfile: (slug, payload) =>
    rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/profile`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  sendWeeklyDigest: (slug, { force = false, previewOnly = false } = {}) => {
    const q = new URLSearchParams({
      force: String(Boolean(force)),
      preview_only: String(Boolean(previewOnly)),
    });
    return rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/digest/send?${q.toString()}`, {
      method: 'POST',
    });
  },

  testShopAlerts: (slug) =>
    rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/alerts/test`, {
      method: 'POST',
    }),

  getShopConnectors: (slug) =>
    callWithPolicy(
      () => rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/connectors`),
      () => ({ scenario_tag: slug, supported_platforms: ['shopee', 'tiktok'], connections: [], platforms: {} })
    ),

  authorizeShopConnector: (slug, platform, redirectUrl) =>
    rawFetchJson(
      `/api/v1/shops/${encodeURIComponent(slug)}/connectors/${encodeURIComponent(platform)}/authorize`,
      {
        method: 'POST',
        body: JSON.stringify({ redirect_url: redirectUrl }),
      }
    ),

  saveManualConnector: (slug, platform, payload) =>
    rawFetchJson(
      `/api/v1/shops/${encodeURIComponent(slug)}/connectors/${encodeURIComponent(platform)}/manual`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  disconnectShopConnector: (slug, platform) =>
    rawFetchJson(
      `/api/v1/shops/${encodeURIComponent(slug)}/connectors/${encodeURIComponent(platform)}`,
      {
        method: 'DELETE',
      }
    ),

  syncShopConnector: (slug, platform, payload = {}) =>
    rawFetchJson(
      `/api/v1/shops/${encodeURIComponent(slug)}/connectors/${encodeURIComponent(platform)}/sync`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  retryPushReply: (replyId) =>
    rawFetchJson(`/api/v1/reviews/replies/${replyId}/retry-push`, {
      method: 'POST',
    }),

  getSkuBreakdown: (scenarioTag = 'real_shop', platform = '', minN = 2, limit = 20) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      min_n: String(minN),
      limit: String(limit),
    });
    if (platform) q.set('platform', platform);
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/stats/sku-breakdown?${q.toString()}`),
      () => ({ scenario_tag: scenarioTag, count: 0, items: [] })
    );
  },

  bulkCreateReplyDrafts: (payload) =>
    rawFetchJson('/api/v1/reviews/bulk-reply-draft', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  bulkUpdateReplyStatus: (payload) =>
    rawFetchJson('/api/v1/reviews/replies/bulk-status', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  triggerAutoReply5Star: (payload) =>
    rawFetchJson('/api/v1/reviews/auto-reply-5star', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  markActionImplemented: (actionId, implementedAt = null) =>
    rawFetchJson(`/api/v1/actions/${actionId}/implemented`, {
      method: 'POST',
      body: JSON.stringify({
        ...(implementedAt ? { implemented_at: implementedAt } : {}),
      }),
    }),

  // Phase 3B: Agency Executive, Owner Team Management, Trial & Billing Quota
  getExecutiveSummary: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/executive/summary'),
      () => ({
        portfolio: {
          total_shops: 0,
          total_reviews: 0,
          portfolio_avg_rating: 0,
          portfolio_neg_rate_pct: 0,
          portfolio_cskh_sla_pct: 100,
          total_pending_cskh: 0,
          total_pending_actions: 0,
        },
        channel_summary: {
          shopee: { reviews: 0, avg_rating: 0, neg_rate_pct: 0 },
          tiktok: { reviews: 0, avg_rating: 0, neg_rate_pct: 0 },
        },
        shops: [],
      })
    ),

  getTeamUsers: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/team/users'),
      () => ({ count: 0, users: [] })
    ),

  createTeamUser: (payload) =>
    rawFetchJson('/api/v1/team/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateTeamUserStatus: (userId, isActive) =>
    rawFetchJson(`/api/v1/team/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: Boolean(isActive) }),
    }),

  createWorkspaceShop: (payload) =>
    rawFetchJson('/api/v1/workspace/shops', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  registerTrial: (payload) =>
    rawFetchJson('/api/v1/auth/register-trial', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getBillingUsage: (scenarioTag = '', monthKey = '') => {
    const q = new URLSearchParams();
    if (scenarioTag) q.set('scenario_tag', scenarioTag);
    if (monthKey) q.set('month_key', monthKey);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/billing/usage${qs}`),
      () => ({
        month_key: '',
        subscription: { plan_code: 'basic', status: 'ACTIVE', monthly_llm_review_limit: 2000, max_shops: 2, max_users: 3 },
        usage: { llm_reviews_used: 0, rule_reviews_used: 0, replies_generated: 0, llm_usage_pct: 0, shops_used: 1, users_used: 1 },
        plans: [],
      })
    );
  },

  // 1. GET /api/v1/health
  getHealth: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/health'),
      () => standaloneEngine.getHealth(),
      true
    ),

  // 2. POST /api/v1/reviews/upload
  uploadReviews: (payload) =>
    callWithPolicy(
      () =>
        rawFetchJson('/api/v1/reviews/upload', {
          method: 'POST',
          body: JSON.stringify(payload),
        }),
      () => standaloneEngine.uploadReviews(payload)
    ),

  // 16. POST /api/v1/reviews/upload-file
  uploadReviewFile: (formData) =>
    callWithPolicy(
      () =>
        rawFetchJson('/api/v1/reviews/upload-file', {
          method: 'POST',
          body: formData,
        }),
      () => standaloneEngine.uploadReviewFile(formData)
    ),

  // 17. GET /api/v1/reviews/{review_id}/replies
  getReviewReplies: (reviewId, scenarioTag = 'real_shop') => {
    const q = new URLSearchParams({ scenario_tag: scenarioTag });
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/replies?${q.toString()}`),
      () => standaloneEngine.getReviewReplies(reviewId, scenarioTag)
    );
  },

  // 18. POST /api/v1/reviews/replies/{reply_id}/status
  updateReplyStatus: (replyId, status, replyText = null) =>
    callWithPolicy(
      () =>
        rawFetchJson(`/api/v1/reviews/replies/${replyId}/status`, {
          method: 'POST',
          body: JSON.stringify({
            status,
            ...(replyText !== null ? { reply_text: replyText } : {}),
          }),
        }),
      () => standaloneEngine.updateReplyStatus(replyId, status, replyText)
    ),

  // 3. POST /api/v1/analyze/run
  runAnalysis: (payload) =>
    callWithPolicy(
      () =>
        rawFetchJson('/api/v1/analyze/run', {
          method: 'POST',
          body: JSON.stringify(payload),
        }),
      () => standaloneEngine.runAnalysis(payload)
    ),

  // 4. GET /api/v1/jobs/{job_id}
  getJobStatus: (jobId) =>
    callWithPolicy(
      () => rawFetchJson(`/api/v1/jobs/${jobId}`),
      () => standaloneEngine.getJobStatus(jobId)
    ),

  // 5. GET /api/v1/stats/overview
  getOverviewStats: (scenarioTag = 'real_shop', minN = 3) =>
    callWithPolicy(
      () =>
        rawFetchJson(
          `/api/v1/stats/overview?scenario_tag=${encodeURIComponent(scenarioTag)}&min_n=${minN}`
        ),
      () => standaloneEngine.getOverviewStats(scenarioTag, minN)
    ),

  // 6. GET /api/v1/insights
  getInsights: (scenarioTag = 'real_shop', kind = '') => {
    const q = new URLSearchParams({ scenario_tag: scenarioTag });
    if (kind) q.set('kind', kind);
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/insights?${q.toString()}`),
      () => standaloneEngine.getInsights(scenarioTag, kind)
    );
  },

  // 7. POST /api/v1/actions/generate
  generateActions: (scenarioTag = 'real_shop', minN = 3, maxActions = 6) =>
    callWithPolicy(
      () =>
        rawFetchJson('/api/v1/actions/generate', {
          method: 'POST',
          body: JSON.stringify({
            scenario_tag: scenarioTag,
            min_n: minN,
            max_actions: maxActions,
          }),
        }),
      () => standaloneEngine.generateActions(scenarioTag, minN, maxActions)
    ),

  // 8. GET /api/v1/actions
  getActions: (
    scenarioTag = 'real_shop',
    isMarketing = null,
    status = '',
    includeArchived = false
  ) => {
    const q = new URLSearchParams({ scenario_tag: scenarioTag });
    if (isMarketing !== null && isMarketing !== undefined && isMarketing !== '') {
      q.set('is_marketing', String(isMarketing));
    }
    if (status) q.set('status', status);
    if (includeArchived) q.set('include_archived', 'true');
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/actions?${q.toString()}`),
      () => standaloneEngine.getActions(scenarioTag, isMarketing, status, includeArchived)
    );
  },

  // 9. POST /api/v1/actions/{action_id}/decision
  submitActionDecision: (actionId, payload) =>
    callWithPolicy(
      () =>
        rawFetchJson(`/api/v1/actions/${actionId}/decision`, {
          method: 'POST',
          body: JSON.stringify(payload),
        }),
      () => standaloneEngine.submitActionDecision(actionId, payload)
    ),

  // 10. GET /api/v1/reviews
  getReviews: ({
    scenarioTag = 'real_shop',
    platform = '',
    aspect = '',
    polarity = '',
    anomalyOnly = false,
    reviewIds = '',
    limit = 50,
    offset = 0,
  } = {}) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      limit: String(limit),
      offset: String(offset),
    });
    if (platform) q.set('platform', platform);
    if (aspect) q.set('aspect', aspect);
    if (polarity) q.set('polarity', polarity);
    if (anomalyOnly) q.set('anomaly_only', 'true');
    if (reviewIds) q.set('review_ids', reviewIds);
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/reviews?${q.toString()}`),
      () =>
        standaloneEngine.getReviews({
          scenarioTag,
          platform,
          aspect,
          polarity,
          reviewIds,
          limit,
          offset,
        })
    );
  },

  // 11. GET /api/v1/trends
  getTrends: (scenarioTag = 'real_shop', period = 'month', aspect = '', minN = 2) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      period,
      min_n: String(minN),
    });
    if (aspect) q.set('aspect', aspect);
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/trends?${q.toString()}`),
      () => standaloneEngine.getTrends(scenarioTag, period, aspect, minN)
    );
  },

  // 12. GET /api/v1/alerts
  getAlerts: (scenarioTag = 'real_shop', period = 'month', minN = 3, minDeltaPp = 8.0) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      period,
      min_n: String(minN),
      min_delta_pp: String(minDeltaPp),
    });
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/alerts?${q.toString()}`),
      () => standaloneEngine.getAlerts(scenarioTag, period, minN, minDeltaPp)
    );
  },

  // 13. POST /api/v1/reviews/{review_id}/reply-draft
  createReplyDraft: (reviewId, scenarioTag = 'real_shop', mode = 'template') => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      mode,
    });
    return callWithPolicy(
      () =>
        rawFetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/reply-draft?${q.toString()}`, {
          method: 'POST',
        }),
      () => standaloneEngine.createReplyDraft(reviewId, scenarioTag, mode)
    );
  },

  // 14. GET /api/v1/actions/{action_id}/impact
  getActionImpact: (actionId, windowDays = 30, since = '', minN = 2) => {
    const q = new URLSearchParams({
      window_days: String(windowDays),
      min_n: String(minN),
    });
    if (since) q.set('since', since);
    return callWithPolicy(
      () => rawFetchJson(`/api/v1/actions/${actionId}/impact?${q.toString()}`),
      () => standaloneEngine.getActionImpact(actionId, windowDays, since, minN)
    );
  },

  // 15. GET /api/v1/reports/export with Auth headers
  downloadReport: async (scenarioTag = 'real_shop', format = 'xlsx') => {
    const { mode, baseUrl } = getConnectionConfig();
    if (mode === 'standalone' || (mode === 'auto' && runtimeStandbyActive)) {
      return standaloneEngine.downloadReport(scenarioTag, format);
    }

    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      format,
    });
    const url = `${baseUrl}/api/v1/reports/export?${q.toString()}`;
    try {
      const res = await fetch(url, {
        credentials: 'include',
        headers: buildHeaders(),
      });
      if (!res.ok) {
        if (mode === 'auto' && (res.status >= 500 || res.status === 404)) {
          runtimeStandbyActive = true;
          return standaloneEngine.downloadReport(scenarioTag, format);
        }
        throw new Error(`Tải báo cáo thất bại (${res.status} ${res.statusText})`);
      }
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      if (format === 'html') {
        window.open(blobUrl, '_blank', 'noopener,noreferrer');
      } else {
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `EcomReview_Report_${scenarioTag}.${format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10000);
    } catch (err) {
      if (mode === 'auto') {
        runtimeStandbyActive = true;
        return standaloneEngine.downloadReport(scenarioTag, format);
      }
      throw err;
    }
  },
};

// CreBy: MenBoyBMN
