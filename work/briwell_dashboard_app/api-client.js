(function attachBriwellApiClient(global) {
  const DEFAULT_BASE = "http://127.0.0.1:8030";

  let writeGate = null;

  function setWriteGate(gateFn) {
    writeGate = typeof gateFn === "function" ? gateFn : null;
  }

  function readConfig() {
    return {
      apiBase: localStorage.getItem("briwell.apiBase") || DEFAULT_BASE,
      role: localStorage.getItem("briwell.role") || "admin",
      email: localStorage.getItem("briwell.email") || "operator@briwell.test",
      bearerToken: localStorage.getItem("briwell.bearerToken") || "",
    };
  }

  function saveConfig(nextConfig) {
    localStorage.setItem("briwell.apiBase", nextConfig.apiBase || DEFAULT_BASE);
    localStorage.setItem("briwell.role", nextConfig.role || "admin");
    if (nextConfig.email) {
      localStorage.setItem("briwell.email", nextConfig.email);
    }
    if (typeof nextConfig.bearerToken === "string") {
      // An explicit empty string clears a previously saved token (log out of
      // the production API); undefined leaves the stored token untouched.
      if (nextConfig.bearerToken) {
        localStorage.setItem("briwell.bearerToken", nextConfig.bearerToken);
      } else {
        localStorage.removeItem("briwell.bearerToken");
      }
    }
  }

  function headers(config) {
    const result = {
      "Content-Type": "application/json",
      "X-User-Role": config.role,
      "X-User-Email": config.email,
    };
    if (config.bearerToken) {
      result.Authorization = `Bearer ${config.bearerToken}`;
    }
    return result;
  }

  async function request(path, options) {
    const config = readConfig();
    const method = options?.method || "GET";
    if (method !== "GET" && writeGate) {
      const allowed = await writeGate({ path, method, apiBase: config.apiBase });
      if (!allowed) {
        const error = new Error(`API ${method} ${path} cancelled by user`);
        error.cancelled = true;
        error.payload = { status: "cancelled_by_user" };
        throw error;
      }
    }
    const body = options?.body === undefined ? undefined : JSON.stringify(options.body);
    const response = await fetch(`${config.apiBase}${path}`, {
      method,
      headers: headers(config),
      body,
    });
    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch (_error) {
        payload = { raw: text };
      }
    }
    if (!response.ok) {
      const error = new Error(`API ${method} ${path} failed with ${response.status}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  global.BriwellApi = {
    readConfig,
    saveConfig,
    request,
    setWriteGate,
    getHealth: () => request("/health"),
    getReadiness: () => request("/ops/readiness"),
    getSourcePolicy: () => request("/discovery/source-policy"),
    getAiProvider: () => request("/ai/provider-status"),
    getTiktokProviderStatus: () => request("/providers/tiktok/status"),
    getTiktokKeywordPlaybook: (params) =>
      request(`/providers/tiktok/keyword-playbook${toQuery(params)}`),
    runTiktokProviderDiscovery: (body) =>
      request("/providers/tiktok/discovery-runs", { method: "POST", body }),
    listCreators: (params) => request(`/creators${toQuery(params)}`),
    importCreators: (body) => request("/creators/import", { method: "POST", body }),
    importVideos: (body) => request("/videos/import", { method: "POST", body }),
    importCreatorProvided: (body) => request("/providers/creator-provided/import", { method: "POST", body }),
    fetchNewsSignals: ({ countries, productCategories, maxItemsPerQuery }) =>
      request(
        `/trends/news?countries=${encodeURIComponent(countries.join(","))}` +
          `&product_categories=${encodeURIComponent(productCategories.join(","))}` +
          `&max_items_per_query=${encodeURIComponent(maxItemsPerQuery || 5)}`
      ),
    listCampaigns: (params) => request(`/campaigns${toQuery(params)}`),
    createCampaign: (body) => request("/campaigns", { method: "POST", body }),
    createDiscoveryPlan: (body) => request("/discovery/plans", { method: "POST", body }),
    prepareOutreachDrafts: (campaignId, body) =>
      request(`/campaigns/${encodeURIComponent(campaignId)}/outreach-drafts`, {
        method: "POST",
        body,
      }),
    runClaimsCheck: (body) => request("/outreach/claims-check", { method: "POST", body }),
    recordStatusTransition: (body) =>
      request("/outreach/status-transition", { method: "POST", body }),
    savePerformanceSnapshot: (body) =>
      request("/performance/snapshots", { method: "POST", body }),
    saveContract: (body) => request("/settlements/contracts", { method: "POST", body }),
    issueDiscountCode: (body) =>
      request("/commerce/discount-codes/issue", { method: "POST", body }),
    listDiscountCodes: (params) => request(`/commerce/discount-codes${toQuery(params)}`),
    issuePortalToken: (body) => request("/portal/tokens", { method: "POST", body }),
    revokePortalTokens: (creatorId) =>
      request(`/portal/tokens/${encodeURIComponent(creatorId)}`, { method: "DELETE" }),
    runRecentPostsScreen: (body) =>
      request("/analysis-jobs/run-recent-posts-screen", { method: "POST", body }),
    saveImportQualityLog: (body) =>
      request("/operations/import-quality-logs", { method: "POST", body }),
    enrichCreators: (body) =>
      request("/operations/creator-enrichment", { method: "POST", body }),
    applyRecentPostsResults: (body) =>
      request("/operations/recent-posts/apply", { method: "POST", body }),
    matchCampaignCandidates: (body) =>
      request("/operations/campaign-match", { method: "POST", body }),
    createOutreachPlan: (body) =>
      request("/operations/outreach-plan", { method: "POST", body }),
    buildOutreachCrmBoard: (body) =>
      request("/operations/outreach-crm/board", { method: "POST", body }),
    createPerformanceRollup: (body) =>
      request("/operations/performance-rollup", { method: "POST", body }),
    runAcquisitionOrchestration: (body) =>
      request("/operations/acquisition-orchestration", { method: "POST", body }),
  };

  function toQuery(params) {
    const query = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "" && value !== "ALL") {
        query.set(key, value);
      }
    });
    const rendered = query.toString();
    return rendered ? `?${rendered}` : "";
  }
})(window);
