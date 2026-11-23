import { standaloneEngine, clearStandaloneOverlay } from './standaloneEngine';

const DEFAULT_ENV_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
export const IS_PRODUCTION_APP =
  (import.meta.env.VITE_APP_MODE || '').trim().toLowerCase() === 'production';
const DEFAULT_ENV_MODE = IS_PRODUCTION_APP
  ? 'remote'
  : import.meta.env.VITE_CONNECTION_MODE || 'auto';

let runtimeStandbyActive = false;

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
    if (response.status === 401) {
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

  getMe: () => rawFetchJson('/api/v1/auth/me'),

  getShops: () =>
    callWithPolicy(
      () => rawFetchJson('/api/v1/shops'),
      () => ({ count: 0, shops: [] })
    ),

  updateShopAlerts: (slug, payload) =>
    rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/alerts`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  testShopAlerts: (slug) =>
    rawFetchJson(`/api/v1/shops/${encodeURIComponent(slug)}/alerts/test`, {
      method: 'POST',
    }),

  markActionImplemented: (actionId, implementedAt = null) =>
    rawFetchJson(`/api/v1/actions/${actionId}/implemented`, {
      method: 'POST',
      body: JSON.stringify({
        ...(implementedAt ? { implemented_at: implementedAt } : {}),
      }),
    }),

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
