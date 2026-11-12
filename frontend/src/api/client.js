const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function buildHeaders(extra = {}) {
  const apiKey = localStorage.getItem('ecomreview_api_key') || '';
  const reviewer = localStorage.getItem('ecomreview_reviewer') || 'chu_shop_aomua';
  const headers = {
    'Content-Type': 'application/json',
    'X-Reviewer': reviewer,
    ...extra,
  };
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  return headers;
}

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: buildHeaders(options.headers),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }
  return response.json();
}

export const api = {
  // 1. GET /api/v1/health
  getHealth: () => request('/api/v1/health'),

  // 2. POST /api/v1/reviews/upload
  uploadReviews: (payload) =>
    request('/api/v1/reviews/upload', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // 3. POST /api/v1/analyze/run
  runAnalysis: (payload) =>
    request('/api/v1/analyze/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // 4. GET /api/v1/jobs/{job_id}
  getJobStatus: (jobId) => request(`/api/v1/jobs/${jobId}`),

  // 5. GET /api/v1/stats/overview
  getOverviewStats: (scenarioTag = 'real_shop', minN = 3) =>
    request(`/api/v1/stats/overview?scenario_tag=${encodeURIComponent(scenarioTag)}&min_n=${minN}`),

  // 6. GET /api/v1/insights
  getInsights: (scenarioTag = 'real_shop', kind = '') => {
    const q = new URLSearchParams({ scenario_tag: scenarioTag });
    if (kind) q.set('kind', kind);
    return request(`/api/v1/insights?${q.toString()}`);
  },

  // 7. POST /api/v1/actions/generate
  generateActions: (scenarioTag = 'real_shop', minN = 3, maxActions = 6) =>
    request('/api/v1/actions/generate', {
      method: 'POST',
      body: JSON.stringify({
        scenario_tag: scenarioTag,
        min_n: minN,
        max_actions: maxActions,
      }),
    }),

  // 8. GET /api/v1/actions
  getActions: (scenarioTag = 'real_shop', isMarketing = null, status = '') => {
    const q = new URLSearchParams({ scenario_tag: scenarioTag });
    if (isMarketing !== null && isMarketing !== undefined && isMarketing !== '') {
      q.set('is_marketing', String(isMarketing));
    }
    if (status) q.set('status', status);
    return request(`/api/v1/actions?${q.toString()}`);
  },

  // 9. POST /api/v1/actions/{action_id}/decision
  submitActionDecision: (actionId, payload) =>
    request(`/api/v1/actions/${actionId}/decision`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

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
    return request(`/api/v1/reviews?${q.toString()}`);
  },

  // 11. GET /api/v1/trends
  getTrends: (scenarioTag = 'real_shop', period = 'month', aspect = '', minN = 2) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      period,
      min_n: String(minN),
    });
    if (aspect) q.set('aspect', aspect);
    return request(`/api/v1/trends?${q.toString()}`);
  },

  // 12. GET /api/v1/alerts
  getAlerts: (scenarioTag = 'real_shop', period = 'month', minN = 3, minDeltaPp = 8.0) => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      period,
      min_n: String(minN),
      min_delta_pp: String(minDeltaPp),
    });
    return request(`/api/v1/alerts?${q.toString()}`);
  },

  // 13. POST /api/v1/reviews/{review_id}/reply-draft
  createReplyDraft: (reviewId, scenarioTag = 'real_shop', mode = 'template') => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      mode,
    });
    return request(`/api/v1/reviews/${encodeURIComponent(reviewId)}/reply-draft?${q.toString()}`, {
      method: 'POST',
    });
  },

  // 14. GET /api/v1/actions/{action_id}/impact
  getActionImpact: (actionId, windowDays = 30, since = '', minN = 2) => {
    const q = new URLSearchParams({
      window_days: String(windowDays),
      min_n: String(minN),
    });
    if (since) q.set('since', since);
    return request(`/api/v1/actions/${actionId}/impact?${q.toString()}`);
  },

  // 15. GET /api/v1/reports/export
  getReportExportUrl: (scenarioTag = 'real_shop', format = 'xlsx') => {
    const q = new URLSearchParams({
      scenario_tag: scenarioTag,
      format,
    });
    return `${API_BASE}/api/v1/reports/export?${q.toString()}`;
  },
};

// CreBy: MenBoyBMN

