(function attachBriwellApiClient(global) {
  const DEFAULT_BASE = "http://127.0.0.1:8030";

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
    if (nextConfig.bearerToken) {
      localStorage.setItem("briwell.bearerToken", nextConfig.bearerToken);
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
    getHealth: () => request("/health"),
    getReadiness: () => request("/ops/readiness"),
    getSourcePolicy: () => request("/discovery/source-policy"),
    getAiProvider: () => request("/ai/provider-status"),
    listCreators: (params) => request(`/creators${toQuery(params)}`),
    importCreators: (body) => request("/creators/import", { method: "POST", body }),
    importVideos: (body) => request("/videos/import", { method: "POST", body }),
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
    runRecentPostsScreen: (body) =>
      request("/analysis-jobs/run-recent-posts-screen", { method: "POST", body }),
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
