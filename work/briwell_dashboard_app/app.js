const state = {
  apiOnline: false,
  systemReadiness: {
    api: "Mock",
    readiness: "Local",
    note: "Local dashboard fallback",
  },
  activeCountry: "ALL",
  selectedCreatorId: "creator-1",
  intakeCreators: [],
  importQuality: null,
  recentPostsByCreator: {
    "creator-1": buildSeedPosts("creator-1", "sunscreen", 20),
    "creator-2": buildSeedPosts("creator-2", "calming_serum", 16),
    "creator-3": buildSeedPosts("creator-3", "cleanser", 12),
  },
  recentScreenResults: {},
  coverageAudit: buildMockCoverageAudit(["MX", "PE", "EC"], "sunscreen", 4),
  recallSafeguards: buildMockRecallSafeguards(),
  creators: [
    {
      creator_id: "creator-1",
      username: "luzskincare",
      display_name: "Luz Skincare",
      country: "MX",
      profile_url: "https://example.com/@luzskincare",
      profile_image_url: "./assets/creator-luz.svg",
      channel_image_url: "./assets/channel-luz.svg",
      follower_count: 48200,
      avg_views: 18600,
      engagement_rate: 6.8,
      platform: "tiktok",
      source_risk_level: "low",
      final_score: 91,
      risk_penalty: 3,
      segment: "review_creator",
      signals: ["SPF Authority", "K-Beauty Fit", "Review Format"],
      recommended_products: ["sunscreen"],
      recommended_campaign_angle:
        "데일리 선케어 루틴, 유기적 리뷰, 구매 링크 전환 설계에 적합한 프리미엄 리뷰 후보",
    },
    {
      creator_id: "creator-2",
      username: "pielconandrea",
      display_name: "Andrea Piel",
      country: "PE",
      profile_url: "https://example.com/@pielconandrea",
      profile_image_url: "./assets/creator-andrea.svg",
      channel_image_url: "./assets/channel-andrea.svg",
      follower_count: 32800,
      avg_views: 12100,
      engagement_rate: 5.4,
      platform: "instagram",
      source_risk_level: "low_medium",
      final_score: 84,
      risk_penalty: 6,
      segment: "beauty_educator",
      signals: ["Education-Led", "Sensitive Skin", "Comment Intent"],
      recommended_products: ["calming_serum", "sunscreen"],
      recommended_campaign_angle:
        "성분 설명과 민감성 피부 루틴 강점 기반 교육형 K-Beauty 캠페인 적합 후보",
    },
    {
      creator_id: "creator-3",
      username: "rutina.ec",
      display_name: "Rutina EC",
      country: "EC",
      profile_url: "https://example.com/@rutina.ec",
      profile_image_url: "./assets/creator-rutina.svg",
      channel_image_url: "./assets/channel-rutina.svg",
      follower_count: 21400,
      avg_views: 9800,
      engagement_rate: 7.2,
      platform: "tiktok",
      source_risk_level: "low",
      final_score: 79,
      risk_penalty: 4,
      segment: "ugc_creator",
      signals: ["UGC Ready", "Routine Demo", "Low Risk"],
      recommended_products: ["cleanser"],
      recommended_campaign_angle:
        "루틴 시연형 콘텐츠 제작 가능성, UGC 확보와 제품 사용감 검증에 적합한 후보",
    },
  ],
  reviewItems: [
    {
      creator: "luzskincare",
      creator_id: "creator-1",
      status: "Brand Safe",
      badge: "green",
      detail: "SPF 리뷰 협업 초안 브랜드 세이프티 검수 통과",
    },
    {
      creator: "pielconandrea",
      creator_id: "creator-2",
      status: "Claims Review",
      badge: "amber",
      detail: "안티에이징 표현, 국가별 화장품 광고 기준 추가 검수 필요",
    },
    {
      creator: "rutina.ec",
      creator_id: "creator-3",
      status: "Contact Check",
      badge: "blue",
      detail: "플랫폼 발송 전 수동 연락 경로와 Do-Not-Contact 상태 확인 필요",
    },
  ],
};

document.addEventListener("DOMContentLoaded", () => {
  hydrateConfigControls();
  bindNavigation();
  bindFilters();
  bindActions();
  renderAll();
  refreshFromApi();
});

function hydrateConfigControls() {
  const config = window.BriwellApi.readConfig();
  byId("apiBaseInput").value = config.apiBase;
  byId("roleSelect").value = config.role;
}

function bindNavigation() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      button.classList.add("active");
      byId(`view-${button.dataset.view}`).classList.add("active");
    });
  });
}

function bindFilters() {
  document.querySelectorAll("[data-country]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-country]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.activeCountry = button.dataset.country;
      renderPriorityTable();
    });
  });

  ["candidateSearch", "candidateCountry", "candidateScore"].forEach((id) => {
    byId(id).addEventListener("input", renderCandidateTable);
  });
}

function bindActions() {
  byId("refreshButton").addEventListener("click", () => {
    window.BriwellApi.saveConfig({
      apiBase: byId("apiBaseInput").value.trim(),
      role: byId("roleSelect").value,
    });
    refreshFromApi();
  });

  byId("runDiscoveryButton").addEventListener("click", runDiscoveryPlan);
  byId("saveCampaignButton").addEventListener("click", saveCampaign);
  byId("prepareDraftsButton").addEventListener("click", prepareDrafts);
  byId("claimsCheckButton").addEventListener("click", runClaimsCheck);
  byId("approveDmButton").addEventListener("click", () =>
    showResult("claimsResult", { status: "approved_for_manual_send" })
  );
  byId("rejectDmButton").addEventListener("click", () =>
    showResult("claimsResult", { status: "rejected", reason: "operator_decision" })
  );
  byId("manualSendButton").addEventListener("click", recordManualSend);
  byId("saveSnapshotButton").addEventListener("click", saveSnapshot);
  byId("saveContractButton").addEventListener("click", saveContract);

  byId("loadCreatorCsvButton").addEventListener("click", loadCreatorCsv);
  byId("importCreatorsButton").addEventListener("click", importCreators);
  byId("loadPostCsvButton").addEventListener("click", loadPostCsv);
  byId("loadManualPostsButton").addEventListener("click", loadManualPosts);
  byId("importVideosButton").addEventListener("click", importVideos);
  byId("runRecentScreenButton").addEventListener("click", () => {
    runRecentScreenForCreator(byId("postCreatorSelect").value);
  });
  byId("postCreatorSelect").addEventListener("change", () => {
    state.selectedCreatorId = byId("postCreatorSelect").value;
    renderPostImportTable();
    renderRecentScreenResult(state.selectedCreatorId);
    renderCandidateTable();
  });
}

async function refreshFromApi() {
  setApiStatus("checking", "API 연결 확인 중");
  try {
    const [health, readiness, sourcePolicy, aiProvider, creators] = await Promise.all([
      window.BriwellApi.getHealth(),
      window.BriwellApi.getReadiness(),
      window.BriwellApi.getSourcePolicy(),
      window.BriwellApi.getAiProvider(),
      window.BriwellApi.listCreators({ limit: 50 }),
    ]);

    state.apiOnline = true;
    setApiStatus("online", "API Online");
    state.systemReadiness = {
      api: health?.status === "ok" ? "Online" : health?.status || "Online",
      readiness: formatReadiness(readiness?.status),
      note: "Connected to live API",
    };
    renderSourcePolicy(sourcePolicy);
    renderAiProvider(aiProvider);

    if (Array.isArray(creators?.items) && creators.items.length > 0) {
      state.creators = mergeCreators(state.creators, creators.items.map(normalizeApiCreator));
    }
  } catch (_error) {
    state.apiOnline = false;
    setApiStatus("offline", "Mock Mode");
    state.systemReadiness = {
      api: "Mock",
      readiness: "Local",
      note: "Local dashboard fallback",
    };
    renderSourcePolicy(null);
    renderAiProvider(null);
  }
  renderAll();
}

function renderAll() {
  renderCommandMetrics();
  renderCommerceCommand();
  renderOperatorActions();
  renderTalentRadar();
  renderPriorityTable();
  renderReviewQueue();
  renderCandidateTable();
  renderPayoutTable();
  renderCreatorImportPreview();
  renderPostCreatorSelect();
  renderPostImportTable();
  renderImportQualityGate();
  renderRecentScreenResult(state.selectedCreatorId);
  renderCoverageAudit();
}

function renderCommandMetrics() {
  const metrics = buildCommandMetrics();
  byId("metricPipelineGmv").textContent = formatCurrencyCompact(metrics.pipelineGmvUsd);
  byId("metricPipelineNote").textContent = `${metrics.targetProgress}% of USD 25K pilot target`;
  byId("metricScreeningCoverage").textContent = `${metrics.loadedRecentPosts}/${metrics.requiredRecentPosts}`;
  byId("metricCoverageNote").textContent = `${metrics.coveragePercent}% recent-post coverage`;
  byId("metricOutreachReady").textContent = String(metrics.outreachReadyCount);
  byId("metricOutreachNote").textContent = `${metrics.screenedCount} screened · ${metrics.lowRiskCount} low-risk candidates`;
  byId("metricQueue").textContent = String(metrics.humanReviewLoad);
  byId("metricQueueNote").textContent = `${metrics.postGapCount} data gaps · ${state.reviewItems.length} approval tasks`;
}

function renderCommerceCommand() {
  const metrics = buildCommandMetrics();
  const stages = [
    ["Discovered", state.creators.length + state.intakeCreators.length, "candidate pool"],
    ["Recent 20", `${metrics.loadedRecentPosts}/${metrics.requiredRecentPosts}`, `${metrics.coveragePercent}% coverage`],
    ["Screened", metrics.screenedCount, "AI first pass"],
    ["Outreach Ready", metrics.outreachReadyCount, "pass + low risk"],
    ["Human Review", metrics.humanReviewLoad, "risk/data gates"],
    ["Live Posts", 0, "tracking pending"],
  ];
  byId("commerceCommand").innerHTML = `
    <div class="command-summary">
      <div>
        <span>Forecast GMV</span>
        <strong>${escapeHtml(formatCurrencyCompact(metrics.pipelineGmvUsd))}</strong>
        <small>${escapeHtml(metrics.targetProgress)}% to pilot target</small>
      </div>
      <div>
        <span>Qualified Reach</span>
        <strong>${escapeHtml(formatCompactNumber(metrics.qualifiedReach))}</strong>
        <small>monthly avg view base</small>
      </div>
      <div>
        <span>Data Confidence</span>
        <strong>${escapeHtml(String(metrics.coveragePercent))}%</strong>
        <small>recent 20 completeness</small>
      </div>
    </div>
    <div class="funnel-board">
      ${stages
        .map(
          ([label, value, note], index) => `
        <div class="funnel-stage" style="--stage-color:${escapeHtml(stageColor(index))}">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
          <small>${escapeHtml(note)}</small>
        </div>
      `
        )
        .join("")}
    </div>
  `;
}

function renderOperatorActions() {
  const metrics = buildCommandMetrics();
  const gapCreators = state.creators.filter((creator) => loadedRecentPostsCount(creator) < 20);
  const readyCreators = state.creators.filter(isOutreachReady);
  const actions = [];

  if (gapCreators.length) {
    actions.push({
      tier: "high",
      label: "Data Completion",
      title: "Recent 20 posts gap",
      detail: gapCreators
        .map((creator) => `@${creator.username} ${loadedRecentPostsCount(creator)}/20`)
        .join(" · "),
      next: "Talent Intake",
    });
  }

  if (readyCreators.length) {
    actions.push({
      tier: "green",
      label: "Outreach",
      title: "DM review-ready talent",
      detail: readyCreators.map((creator) => `@${creator.username}`).join(" · "),
      next: "Brand Safety Desk",
    });
  }

  const auditRisk = (state.coverageAudit || []).filter((item) => (item.missing_intent_types || []).length > 0);
  if (auditRisk.length) {
    actions.push({
      tier: "blue",
      label: "Discovery Recall",
      title: "Second-pass expansion",
      detail: `${auditRisk.length} market/category cells have missing intent coverage`,
      next: "Creator Discovery",
    });
  }

  actions.push({
    tier: state.apiOnline ? "green" : "neutral",
    label: "System",
    title: `${state.systemReadiness.api} · ${state.systemReadiness.readiness}`,
    detail: state.systemReadiness.note,
    next: `${formatCompactNumber(metrics.qualifiedReach)} qualified view base`,
  });

  byId("operatorActions").innerHTML = actions
    .slice(0, 4)
    .map(
      (action) => `
      <article class="action-card ${escapeHtml(action.tier)}">
        <span>${escapeHtml(action.label)}</span>
        <strong>${escapeHtml(action.title)}</strong>
        <p>${escapeHtml(action.detail)}</p>
        <small>${escapeHtml(action.next)}</small>
      </article>
    `
    )
    .join("");
}

function buildCommandMetrics() {
  const creators = state.creators;
  const requiredRecentPosts = Math.max(0, creators.length * 20);
  const loadedRecentPosts = creators.reduce((sum, creator) => sum + loadedRecentPostsCount(creator), 0);
  const coveragePercent = requiredRecentPosts ? Math.round((loadedRecentPosts / requiredRecentPosts) * 100) : 0;
  const screenedCount = Object.keys(state.recentScreenResults).length;
  const lowRiskCount = creators.filter((creator) => ["low", "low_medium"].includes(sourceRiskForCreator(creator.creator_id))).length;
  const outreachReadyCount = creators.filter(isOutreachReady).length;
  const postGapCount = creators.filter((creator) => loadedRecentPostsCount(creator) < 20).length;
  const explicitReviewCount = Object.values(state.recentScreenResults).filter((result) =>
    ["human_review", "avoid"].includes(result.suitability_decision)
  ).length;
  const humanReviewLoad = state.reviewItems.length + postGapCount + explicitReviewCount;
  const qualifiedReach = creators.reduce((sum, creator) => sum + Number(creator.avg_views || 0), 0);
  const budget = toNumber(byId("campaignBudget")?.value || 1200);
  const pipelineGmvUsd = Math.round((qualifiedReach * 0.45 + outreachReadyCount * budget) / 100) * 100;
  const targetProgress = Math.min(100, Math.round((pipelineGmvUsd / 25000) * 100));
  return {
    requiredRecentPosts,
    loadedRecentPosts,
    coveragePercent,
    screenedCount,
    lowRiskCount,
    outreachReadyCount,
    postGapCount,
    explicitReviewCount,
    humanReviewLoad,
    qualifiedReach,
    pipelineGmvUsd,
    targetProgress,
  };
}

function evaluateImportQuality() {
  const creatorCandidates = state.intakeCreators.length ? state.intakeCreators : state.creators;
  const creatorIssues = validateCreatorDataset(creatorCandidates);
  const postIssues = validateRecentPostDataset(creatorCandidates);
  const blockerCount = creatorIssues.blockers.length + postIssues.blockers.length;
  const warningCount = creatorIssues.warnings.length + postIssues.warnings.length;
  let overallStatus = "ready";
  if (blockerCount > 0) {
    overallStatus = "blocked";
  } else if (warningCount > 0) {
    overallStatus = "needs_review";
  }
  return {
    overall_status: overallStatus,
    summary: buildQualitySummary(overallStatus, blockerCount, warningCount),
    creator: creatorIssues,
    posts: postIssues,
  };
}

function validateCreatorDataset(creators) {
  const blockers = [];
  const warnings = [];
  const seenUsernames = new Set();
  const seenProfiles = new Set();
  const marketCoverage = [];
  const invalidCreatorIds = new Set();

  creators.forEach((creator, index) => {
    const rowLabel = creator.username ? `@${creator.username}` : `row ${index + 1}`;
    const creatorKey = creator.creator_id || creator.username || `row-${index}`;
    if (!creator.username) {
      blockers.push(`${rowLabel}: username required`);
      invalidCreatorIds.add(creatorKey);
    }
    if (!creator.profile_url) {
      blockers.push(`${rowLabel}: profile_url required`);
      invalidCreatorIds.add(creatorKey);
    }
    if (!["MX", "PE", "EC"].includes(creator.country)) {
      blockers.push(`${rowLabel}: country must be MX, PE, or EC`);
      invalidCreatorIds.add(creatorKey);
    }
    if (!["low", "low_medium", "medium"].includes(normalizeRisk(creator.source_risk_level))) {
      blockers.push(`${rowLabel}: source_risk_level must be low, low_medium, or medium`);
      invalidCreatorIds.add(creatorKey);
    }
    if (!creator.follower_count) warnings.push(`${rowLabel}: follower_count missing`);
    if (!creator.avg_views) warnings.push(`${rowLabel}: avg_views missing`);
    if (!creator.profile_image_url || creator.profile_image_url.includes("creator-luz.svg")) {
      warnings.push(`${rowLabel}: profile image should be replaced with channel-provided asset`);
    }

    const usernameKey = String(creator.username || "").toLowerCase();
    const profileKey = String(creator.profile_url || "").toLowerCase();
    if (usernameKey && seenUsernames.has(usernameKey)) {
      blockers.push(`${rowLabel}: duplicate username`);
      invalidCreatorIds.add(creatorKey);
    }
    if (profileKey && seenProfiles.has(profileKey)) {
      blockers.push(`${rowLabel}: duplicate profile_url`);
      invalidCreatorIds.add(creatorKey);
    }
    if (usernameKey) seenUsernames.add(usernameKey);
    if (profileKey) seenProfiles.add(profileKey);
  });

  ["MX", "PE", "EC"].forEach((country) => {
    if (creators.some((creator) => creator.country === country)) {
      marketCoverage.push(country);
    } else {
      warnings.push(`${country}: no creator candidate loaded`);
    }
  });

  return {
    total: creators.length,
    valid: Math.max(0, creators.length - invalidCreatorIds.size),
    market_coverage: marketCoverage,
    blockers: unique(blockers),
    warnings: unique(warnings),
    readiness: creators.map((creator) => {
      const postCount = loadedRecentPostsCount(creator);
      return {
        username: creator.username || creator.creator_id || "creator",
        post_count: postCount,
        status: postCount >= 20 ? "Ready" : postCount > 0 ? "Needs more posts" : "No recent posts",
      };
    }),
  };
}

function validateRecentPostDataset(creators) {
  const blockers = [];
  const warnings = [];
  let loaded = 0;
  const required = Math.max(0, creators.length * 20);

  creators.forEach((creator) => {
    const posts = state.recentPostsByCreator[creator.creator_id] || [];
    loaded += Math.min(20, posts.length);
    if (posts.length === 0) {
      blockers.push(`@${creator.username}: recent 20 posts missing`);
      return;
    }
    if (posts.length < 20) {
      blockers.push(`@${creator.username}: ${posts.length}/20 recent posts loaded`);
    }
    const duplicateUrls = findDuplicates(posts.map((post) => post.url).filter(Boolean));
    duplicateUrls.forEach((url) => blockers.push(`@${creator.username}: duplicate post URL ${url}`));
    const missingUrls = posts.filter((post) => !post.url).length;
    const missingCaptions = posts.filter((post) => !post.caption).length;
    const missingMetrics = posts.filter((post) => !post.view_count && !post.like_count && !post.comment_count).length;
    const missingTranscripts = posts.filter((post) => !post.transcript).length;
    if (missingUrls) blockers.push(`@${creator.username}: ${missingUrls} posts missing URL`);
    if (missingCaptions) warnings.push(`@${creator.username}: ${missingCaptions} posts missing captions`);
    if (missingMetrics) warnings.push(`@${creator.username}: ${missingMetrics} posts missing public metrics`);
    if (missingTranscripts) warnings.push(`@${creator.username}: ${missingTranscripts} posts missing transcripts`);
  });

  return {
    loaded,
    required,
    coverage_percent: required ? Math.round((loaded / required) * 100) : 0,
    blockers: unique(blockers),
    warnings: unique(warnings),
  };
}

function buildQualitySummary(status, blockers, warnings) {
  if (status === "blocked") return `${blockers} blockers must be fixed before import or screening.`;
  if (status === "needs_review") return `${warnings} warnings need operator review before outreach.`;
  return "Ready for import, screening, and operator review.";
}

function loadedRecentPostsCount(creator) {
  return Math.min(20, (state.recentPostsByCreator[creator.creator_id] || []).length);
}

function isOutreachReady(creator) {
  const result = state.recentScreenResults[creator.creator_id];
  const lowRisk = ["low", "low_medium"].includes(sourceRiskForCreator(creator.creator_id));
  const productMatched = Boolean(
    (result?.matched_product_categories || creator.recommended_products || []).length
  );
  if (result?.suitability_decision) {
    return result.suitability_decision === "pass_to_full_analysis" && lowRisk && productMatched;
  }
  return Number(creator.final_score || 0) >= 88 && lowRisk && productMatched && loadedRecentPostsCount(creator) >= 20;
}

function stageColor(index) {
  return ["#2457c5", "#0e7490", "#047857", "#6d28d9", "#b45309", "#667085"][index] || "#2457c5";
}

function qualityStatusClass(status) {
  if (status === "ready") return "quality-ready";
  if (status === "needs_review") return "quality-review";
  return "quality-blocked";
}

function formatQualityStatus(status) {
  const labels = {
    ready: "Ready",
    needs_review: "Needs Review",
    blocked: "Blocked",
  };
  return labels[status] || status;
}

function findDuplicates(values) {
  const seen = new Set();
  const duplicates = new Set();
  values.forEach((value) => {
    const key = String(value || "").trim().toLowerCase();
    if (!key) return;
    if (seen.has(key)) duplicates.add(value);
    seen.add(key);
  });
  return Array.from(duplicates);
}

function renderTalentRadar() {
  const radar = byId("talentRadar");
  if (!radar) return;
  radar.innerHTML = state.creators
    .slice()
    .sort((left, right) => Number(right.final_score || 0) - Number(left.final_score || 0))
    .slice(0, 3)
    .map(
      (creator) => `
      <button class="talent-radar-card" data-select-creator="${escapeHtml(creator.creator_id)}">
        <img class="radar-cover" src="${escapeHtml(channelImage(creator))}" alt="${escapeHtml(creator.display_name || creator.username)} channel image">
        <span class="radar-market">${escapeHtml(formatMarket(creator.country))}</span>
        <div class="radar-content">
          ${avatarImage(creator, "profile-avatar radar-avatar")}
          <div>
            <strong>@${escapeHtml(creator.username)}</strong>
            <span>${escapeHtml(formatSegment(creator.segment || "review_creator"))}</span>
          </div>
        </div>
        <div class="radar-footer">
          <span>Fit ${escapeHtml(String(creator.final_score || 0))}</span>
          <span>${escapeHtml(formatCompactNumber(creator.avg_views))} avg views</span>
          <span>${escapeHtml(formatPercent(creator.engagement_rate))} ER</span>
        </div>
      </button>
    `
    )
    .join("");
  bindCreatorOpenButtons();
}

function renderPriorityTable() {
  const rows = filteredCreators()
    .sort((left, right) => Number(right.final_score || 0) - Number(left.final_score || 0))
    .map(
      (creator) => `
      <tr class="${creator.creator_id === state.selectedCreatorId ? "row-selected" : ""}">
        <td>${talentCell(creator)}</td>
        <td>${escapeHtml(formatMarket(creator.country))}</td>
        <td>${scoreCell(creator.final_score)}</td>
        <td>${riskBadge(creator.source_risk_level)}</td>
        <td>${escapeHtml(formatSegment(creator.segment || "review_creator"))}</td>
        <td><button class="button" data-select-creator="${escapeHtml(creator.creator_id)}">Review</button></td>
      </tr>
    `
    )
    .join("");
  byId("priorityTable").innerHTML = rows || emptyRow(6, "조건에 맞는 우선 후보 없음");
  bindCreatorOpenButtons();
}

function renderReviewQueue() {
  byId("reviewQueue").innerHTML = state.reviewItems
    .map((item) => {
      const creator = findCreatorForReview(item);
      return `
      <article class="queue-item">
        <div class="queue-top">
          <div class="queue-talent">
            ${avatarImage(creator, "queue-avatar")}
            <div>
              <strong>@${escapeHtml(item.creator)}</strong>
              <span>${escapeHtml(formatMarket(creator?.country || ""))}</span>
            </div>
          </div>
          <span class="badge ${escapeHtml(item.badge)}">${escapeHtml(item.status)}</span>
        </div>
        <p class="muted">${escapeHtml(item.detail)}</p>
      </article>
    `;
    })
    .join("");
}

function renderCandidateTable() {
  const search = byId("candidateSearch").value.trim().toLowerCase();
  const country = byId("candidateCountry").value;
  const minScore = Number(byId("candidateScore").value);
  const candidates = state.creators.filter((creator) => {
    const matchesCountry = country === "ALL" || creator.country === country;
    const matchesScore = Number(creator.final_score || 0) >= minScore;
    const text = `${creator.username} ${creator.display_name || ""} ${creator.signals?.join(" ") || ""}`.toLowerCase();
    return matchesCountry && matchesScore && text.includes(search);
  });

  const selected = candidates.find((creator) => creator.creator_id === state.selectedCreatorId) || candidates[0] || state.creators[0];
  if (selected) {
    state.selectedCreatorId = selected.creator_id;
  }

  byId("candidateTable").innerHTML =
    candidates
      .map(
        (creator) => `
      <tr class="${creator.creator_id === state.selectedCreatorId ? "row-selected" : ""}">
        <td>${talentCell(creator)}</td>
        <td>${audienceCell(creator)}</td>
        <td>${scoreCell(creator.final_score)}</td>
        <td>${signalTags(creator.signals)}</td>
        <td><button class="button" data-select-creator="${escapeHtml(creator.creator_id)}">Open Profile</button></td>
      </tr>
    `
      )
      .join("") || emptyRow(5, "조건에 맞는 인플루언서 없음");
  bindCreatorOpenButtons();
  renderCandidateDetail(selected);
}

function renderCandidateDetail(creator) {
  if (!creator) {
    byId("candidateDetail").innerHTML = "";
    return;
  }
  const screen = state.recentScreenResults[creator.creator_id];
  byId("candidateDetail").innerHTML = `
    <div class="creator-cover-wrap">
      <img class="creator-cover" src="${escapeHtml(channelImage(creator))}" alt="${escapeHtml(creator.display_name || creator.username)} channel image">
      <div class="creator-avatar-overlap">${avatarImage(creator, "profile-avatar large")}</div>
    </div>
    <div class="detail-title-row">
      <div>
        <h3>@${escapeHtml(creator.username)}</h3>
        <div class="muted">${escapeHtml(creator.display_name || "")} · ${escapeHtml(formatMarket(creator.country))} · ${escapeHtml(formatPlatform(creator.platform || ""))}</div>
      </div>
      ${riskBadge(creator.source_risk_level)}
    </div>
    <div class="creator-stat-grid">
      <div><span>Followers</span><strong>${escapeHtml(formatCompactNumber(creator.follower_count))}</strong></div>
      <div><span>Avg Views</span><strong>${escapeHtml(formatCompactNumber(creator.avg_views))}</strong></div>
      <div><span>Engagement</span><strong>${escapeHtml(formatPercent(creator.engagement_rate))}</strong></div>
      <div><span>Fit Score</span><strong>${escapeHtml(String(creator.final_score || 0))}</strong></div>
    </div>
    <div class="signal-list">${signalTags(creator.signals)}</div>
    <div class="policy-line"><span>Risk Penalty</span><strong>${escapeHtml(String(creator.risk_penalty || 0))}</strong></div>
    <div class="policy-line"><span>Best Format</span><strong>${escapeHtml(formatSegment(creator.segment || "review_creator"))}</strong></div>
    <p>${escapeHtml(creator.recommended_campaign_angle || "협업 전 최종 검수 필요")}</p>
    ${screen ? renderScreenCompact(screen) : renderScreenPlaceholder(creator.creator_id)}
    <div class="detail-actions">
      <button class="button primary" data-add-to-campaign="${escapeHtml(creator.creator_id)}">Shortlist Talent</button>
      <button class="button" data-run-recent-screen="${escapeHtml(creator.creator_id)}">Run Recent 20 Posts Screen</button>
    </div>
  `;
  bindShortlistButtons();
  bindRecentScreenButtons();
}

function renderSourcePolicy(payload) {
  const source = payload || {
    allowed_source_types: ["manual", "official_api", "approved_provider", "creator_provided"],
    blocked_source_types: ["browser_automation", "captcha_bypass", "public_page_scrape"],
    policy: "Unauthorized scraping is blocked in MVP v0.1.",
  };
  byId("sourcePolicy").innerHTML = `
    <div class="policy-line"><span>Allowed Sources</span><strong>${escapeHtml(formatSourceTypes(source.allowed_source_types).join(", "))}</strong></div>
    <div class="policy-line"><span>Blocked Sources</span><strong>${escapeHtml(formatSourceTypes(source.blocked_source_types).join(", "))}</strong></div>
    <div>${escapeHtml(formatPolicyText(source.policy))}</div>
  `;
}

function renderAiProvider(payload) {
  const source = payload || {
    provider: "google",
    default_adapter: "GeminiTextAdapter",
    live_ready: false,
    dry_run: true,
  };
  byId("aiProvider").innerHTML = `
    <div class="policy-line"><span>Primary Provider</span><strong>${escapeHtml(formatProvider(source.provider || "google"))}</strong></div>
    <div class="policy-line"><span>Adapter</span><strong>${escapeHtml(formatAdapter(source.default_adapter || "GeminiTextAdapter"))}</strong></div>
    <div class="policy-line"><span>Live Calls</span><strong>${escapeHtml(formatBoolean(Boolean(source.live_ready)))}</strong></div>
    <div class="policy-line"><span>Dry Run</span><strong>${escapeHtml(formatBoolean(Boolean(source.dry_run)))}</strong></div>
  `;
}

function renderPayoutTable() {
  const rows = [
    ["@luzskincare", "$150", "pending", "Post URL"],
    ["@pielconandrea", "$220", "blocked", "Invoice URL"],
    ["@rutina.ec", "$120", "pending", "Tax Document"],
  ];
  byId("payoutTable").innerHTML = rows
    .map(
      ([creator, amount, status, blocker]) => `
      <tr>
        <td>${escapeHtml(creator)}</td>
        <td>${escapeHtml(amount)}</td>
        <td>${status === "blocked" ? '<span class="badge red">Blocked</span>' : '<span class="badge amber">Pending</span>'}</td>
        <td>${escapeHtml(blocker)}</td>
      </tr>
    `
    )
    .join("");
}

function renderCreatorImportPreview() {
  const rows = state.intakeCreators.slice(0, 12).map(
    (creator) => `
      <tr>
        <td>${talentCell(creator)}</td>
        <td>${escapeHtml(formatMarket(creator.country))}</td>
        <td>${escapeHtml(formatCompactNumber(creator.follower_count))}</td>
        <td>${riskBadge(creator.source_risk_level)}</td>
      </tr>
    `
  );
  byId("creatorImportTable").innerHTML = rows.join("") || emptyRow(4, "업로드한 후보 CSV 미리보기 없음");
}

function renderPostCreatorSelect() {
  const select = byId("postCreatorSelect");
  const previous = select.value || state.selectedCreatorId;
  select.innerHTML = state.creators
    .map(
      (creator) =>
        `<option value="${escapeHtml(creator.creator_id)}">@${escapeHtml(creator.username)} · ${escapeHtml(formatMarket(creator.country))}</option>`
    )
    .join("");
  select.value = state.creators.some((creator) => creator.creator_id === previous)
    ? previous
    : state.creators[0]?.creator_id || "";
}

function renderPostImportTable() {
  const creatorId = byId("postCreatorSelect").value || state.selectedCreatorId;
  const posts = (state.recentPostsByCreator[creatorId] || []).slice(0, 20);
  byId("postImportTable").innerHTML =
    posts
      .map(
        (post, index) => `
      <tr>
        <td>
          <strong>${escapeHtml(post.platform_video_id || post.video_id || `post-${index + 1}`)}</strong>
          <span class="table-subtext">${escapeHtml(truncate(post.caption || post.url || "", 82))}</span>
        </td>
        <td>${escapeHtml(formatCompactNumber(post.view_count))}</td>
        <td>${escapeHtml(formatCompactNumber(Number(post.like_count || 0) + Number(post.comment_count || 0) + Number(post.share_count || 0)))}</td>
        <td>${signalTags((post.hashtags || []).slice(0, 3))}</td>
      </tr>
    `
      )
      .join("") || emptyRow(4, "최근 게시물 데이터 없음");
}

function renderImportQualityGate() {
  const gate = byId("importQualityGate");
  if (!gate) return;
  const quality = evaluateImportQuality();
  state.importQuality = quality;
  gate.innerHTML = `
    <div class="quality-summary">
      <article class="${escapeHtml(qualityStatusClass(quality.overall_status))}">
        <span>Overall Status</span>
        <strong>${escapeHtml(formatQualityStatus(quality.overall_status))}</strong>
        <small>${escapeHtml(quality.summary)}</small>
      </article>
      <article>
        <span>Creator Data</span>
        <strong>${escapeHtml(String(quality.creator.total))}</strong>
        <small>${escapeHtml(quality.creator.valid)} valid · ${escapeHtml(quality.creator.blockers.length)} blockers</small>
      </article>
      <article>
        <span>Recent Posts</span>
        <strong>${escapeHtml(String(quality.posts.loaded))}/${escapeHtml(String(quality.posts.required))}</strong>
        <small>${escapeHtml(quality.posts.coverage_percent)}% coverage · ${escapeHtml(quality.posts.blockers.length)} blockers</small>
      </article>
      <article>
        <span>Market Coverage</span>
        <strong>${escapeHtml(quality.creator.market_coverage.join(" · ") || "None")}</strong>
        <small>MX, PE, EC launch cluster</small>
      </article>
    </div>
    <div class="quality-columns">
      ${renderQualityColumn("Creator Blockers", quality.creator.blockers, "red")}
      ${renderQualityColumn("Creator Warnings", quality.creator.warnings, "amber")}
      ${renderQualityColumn("Post Blockers", quality.posts.blockers, "red")}
      ${renderQualityColumn("Post Warnings", quality.posts.warnings, "amber")}
    </div>
    <div class="quality-readiness">
      ${quality.creator.readiness
        .map(
          (item) => `
        <div>
          <span>@${escapeHtml(item.username)}</span>
          <strong>${escapeHtml(String(item.post_count))}/20</strong>
          <small>${escapeHtml(item.status)}</small>
        </div>
      `
        )
        .join("")}
    </div>
  `;
}

function renderQualityColumn(title, items, tone) {
  const rendered = items.length
    ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : `<li class="quality-empty">Clear</li>`;
  return `
    <section class="quality-column ${escapeHtml(tone)}">
      <h3>${escapeHtml(title)}</h3>
      <ul>${rendered}</ul>
    </section>
  `;
}

function renderRecentScreenResult(creatorId) {
  const result = state.recentScreenResults[creatorId];
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  const posts = state.recentPostsByCreator[creatorId] || [];
  const target = byId("recentScreenResult");
  if (!target) return;
  if (!result) {
    target.innerHTML = `
      <div class="screening-empty">
        <strong>${creator ? `@${escapeHtml(creator.username)}` : "Target Talent"}</strong>
        <span>${escapeHtml(posts.length)} / 20 recent posts loaded</span>
        <p class="muted">CSV 또는 수동 입력 후 Run Recent 20 Posts Screen으로 1차 적합성을 확인</p>
      </div>
    `;
    return;
  }
  target.innerHTML = renderScreenFull(result, creator, posts.length);
}

function renderCoverageAudit() {
  const audit = state.coverageAudit || [];
  byId("coverageAudit").innerHTML =
    audit
      .map(
        (item) => `
      <article class="audit-card">
        <div class="audit-card-top">
          <strong>${escapeHtml(formatMarket(item.country))}</strong>
          <span>${escapeHtml(formatProductCategory(item.product_category))}</span>
        </div>
        <div class="audit-metrics">
          <div><span>Selected</span><strong>${escapeHtml(String(item.selected_count || 0))}</strong></div>
          <div><span>Available</span><strong>${escapeHtml(String(item.available_count || 0))}</strong></div>
          <div><span>Missing</span><strong>${escapeHtml(String((item.missing_intent_types || []).length))}</strong></div>
        </div>
        <div class="tag-row">${(item.missing_intent_types || []).map((value) => `<span class="badge amber">${escapeHtml(formatIntent(value))}</span>`).join("") || '<span class="badge green">Balanced</span>'}</div>
        <p>${escapeHtml((item.false_negative_risks || [])[0] || "초기 조건으로 인한 누락 리스크 낮음")}</p>
        <small>${escapeHtml((item.recommended_actions || [])[0] || "최근 20개 게시물 스크리닝으로 최종 제외 전 확인")}</small>
      </article>
    `
      )
      .join("") || `<div class="screening-empty"><strong>Coverage audit 없음</strong><span>Discovery brief 생성 후 표시</span></div>`;

  byId("recallSafeguards").innerHTML = (state.recallSafeguards || [])
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
}

async function runDiscoveryPlan() {
  const countries = Array.from(byId("discoveryCountries").selectedOptions).map((item) => item.value);
  const product = byId("discoveryProduct").value;
  const platform = byId("discoveryPlatform").value;
  const limit = Number(byId("discoveryLimit").value || 4);
  const fallback = buildMockDiscoveryRows(countries, product, platform, limit);

  try {
    const payload = await window.BriwellApi.createDiscoveryPlan({
      countries,
      product_categories: [product],
      platforms: [platform],
      max_keywords_per_country_category: limit,
      include_coverage_audit: true,
    });
    renderDiscoveryRows(payload.items || fallback);
    state.coverageAudit = payload.coverage_audit || buildMockCoverageAudit(countries, product, limit);
    state.recallSafeguards = payload.recall_safeguards || buildMockRecallSafeguards();
    renderCoverageAudit();
  } catch (_error) {
    renderDiscoveryRows(fallback);
    state.coverageAudit = buildMockCoverageAudit(countries, product, limit);
    state.recallSafeguards = buildMockRecallSafeguards();
    renderCoverageAudit();
  }
}

async function loadCreatorCsv() {
  try {
    const text = await readFileInput("creatorCsvInput");
    state.intakeCreators = parseCsv(text).map(normalizeCsvCreator);
    renderCreatorImportPreview();
    renderImportQualityGate();
    showResult("creatorImportResult", {
      status: "preview_ready",
      preview_count: state.intakeCreators.length,
      source_risk_level: highestRiskLevel(state.intakeCreators),
    });
    showToast(`${state.intakeCreators.length} creator candidates loaded`);
  } catch (error) {
    showResult("creatorImportResult", { status: "preview_failed", message: error.message });
  }
}

async function importCreators() {
  if (!state.intakeCreators.length) {
    showResult("creatorImportResult", { status: "empty", message: "Preview a creator CSV before import." });
    return;
  }
  const payload = {
    source_type: "manual",
    source_risk_level: highestRiskLevel(state.intakeCreators),
    items: state.intakeCreators.map(toCreatorImportItem),
  };
  try {
    const response = await window.BriwellApi.importCreators(payload);
    const imported = Array.isArray(response.items) && response.items.length
      ? response.items.map((item, index) => normalizeApiCreator({ ...state.intakeCreators[index], ...item }))
      : state.intakeCreators;
    state.creators = mergeCreators(state.creators, imported);
    showResult("creatorImportResult", response);
  } catch (error) {
    state.creators = mergeCreators(state.creators, state.intakeCreators);
    showResult("creatorImportResult", error.payload || { status: "mock_imported", accepted: state.intakeCreators.length });
  }
  renderAll();
  showToast("Creator import workflow completed");
}

async function loadPostCsv() {
  try {
    const creatorId = byId("postCreatorSelect").value;
    const text = await readFileInput("postCsvInput");
    const posts = parseCsv(text).map((row, index) => normalizeCsvPost(row, creatorId, index));
    state.recentPostsByCreator[creatorId] = posts.slice(0, 20);
    renderPostImportTable();
    renderImportQualityGate();
    renderRecentScreenResult(creatorId);
    showResult("postImportResult", {
      status: "preview_ready",
      creator_id: creatorId,
      recent_posts_loaded: state.recentPostsByCreator[creatorId].length,
    });
  } catch (error) {
    showResult("postImportResult", { status: "preview_failed", message: error.message });
  }
}

function loadManualPosts() {
  try {
    const creatorId = byId("postCreatorSelect").value;
    const text = byId("manualPostsInput").value.trim();
    const rows = parseManualPosts(text);
    const posts = rows.map((row, index) => normalizeCsvPost(row, creatorId, index));
    state.recentPostsByCreator[creatorId] = posts.slice(0, 20);
    renderPostImportTable();
    renderImportQualityGate();
    renderRecentScreenResult(creatorId);
    showResult("postImportResult", {
      status: "manual_preview_ready",
      creator_id: creatorId,
      recent_posts_loaded: state.recentPostsByCreator[creatorId].length,
    });
  } catch (error) {
    showResult("postImportResult", { status: "manual_preview_failed", message: error.message });
  }
}

async function importVideos() {
  const creatorId = byId("postCreatorSelect").value;
  const posts = (state.recentPostsByCreator[creatorId] || []).slice(0, 20);
  if (!creatorId || !posts.length) {
    showResult("postImportResult", { status: "empty", message: "Load recent posts before video import." });
    return;
  }
  const payload = {
    creator_id: creatorId,
    source_type: "manual",
    source_risk_level: sourceRiskForCreator(creatorId),
    items: posts.map(toVideoImportItem),
  };
  try {
    showResult("postImportResult", await window.BriwellApi.importVideos(payload));
  } catch (error) {
    showResult("postImportResult", error.payload || { status: "mock_imported", creator_id: creatorId, accepted: posts.length });
  }
  showToast(`${posts.length} recent posts linked to candidate`);
}

async function runRecentScreenForCreator(creatorId) {
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  const posts = (state.recentPostsByCreator[creatorId] || []).slice(0, 20);
  if (!creator) return;

  if (!posts.length) {
    const output = buildNoPostsScreenResult();
    state.recentScreenResults[creatorId] = output;
    renderRecentScreenResult(creatorId);
    renderCandidateDetail(creator);
    showResult("postImportResult", { status: "missing_recent_posts", output });
    return;
  }

  const payload = {
    creator_id: creatorId,
    source_risk_level: sourceRiskForCreator(creatorId),
    recent_posts: posts.map(toRecentPostSnapshot),
    expected_post_count: 20,
    creator_snapshot: creatorSnapshot(creator),
    product_context: {
      product_category: byId("campaignProduct")?.value || "sunscreen",
      brand: "Briwell",
      markets: ["MX", "PE", "EC"],
    },
    dry_run: true,
  };

  try {
    const response = await window.BriwellApi.runRecentPostsScreen(payload);
    const output = extractRecentScreenOutput(response) || mockRecentPostsScreen(creator, posts);
    state.recentScreenResults[creatorId] = output;
    applyScreenResultToCreator(creatorId, output);
    showResult("postImportResult", { status: "screened", creator_id: creatorId, output });
  } catch (error) {
    const output = extractRecentScreenOutput(error.payload) || mockRecentPostsScreen(creator, posts);
    state.recentScreenResults[creatorId] = output;
    applyScreenResultToCreator(creatorId, output);
    showResult("postImportResult", error.payload || { status: "mock_screened", creator_id: creatorId, output });
  }
  renderAll();
  document.querySelector('[data-view="intake"]').click();
  showToast(`@${creator.username} recent 20 posts screened`);
}

async function saveCampaign() {
  const payload = {
    name: byId("campaignName").value.trim(),
    country: byId("campaignCountry").value,
    product_category: byId("campaignProduct").value,
    campaign_goal: byId("campaignGoal").value.trim(),
    budget: Number(byId("campaignBudget").value || 0),
    sales_channel: byId("campaignChannel").value,
    status: "draft",
  };
  try {
    showResult("campaignSaveResult", await window.BriwellApi.createCampaign(payload));
  } catch (error) {
    showResult("campaignSaveResult", error.payload || { status: "mock_saved", campaign: payload });
  }
}

async function prepareDrafts() {
  const selected = state.creators.slice(0, 2);
  const payload = {
    product_category: byId("campaignProduct").value,
    product_name: "Briwell Daily Sun",
    dm_variant: "product_review",
    candidate_snapshots: selected.map(creatorSnapshot),
  };
  try {
    showResult("draftResult", await window.BriwellApi.prepareOutreachDrafts("campaign-1", payload));
  } catch (error) {
    showResult("draftResult", error.payload || { status: "mock_prepared", prepared_count: selected.length });
  }
}

async function runClaimsCheck() {
  const payload = {
    product_category: byId("claimProduct").value,
    dm_message: byId("dmMessage").value.trim(),
  };
  try {
    showResult("claimsResult", await window.BriwellApi.runClaimsCheck(payload));
  } catch (error) {
    showResult("claimsResult", error.payload || { status: "mock_passed", safe_to_send: true });
  }
}

async function recordManualSend() {
  const payload = {
    current_status: "approved",
    next_status: "dm_sent",
    claims_check_status: "passed",
    do_not_contact_checked: true,
    manual_send_confirmed: true,
    operator_notes: "Manual send completed by operator in the platform app.",
  };
  try {
    showResult("manualSendResult", await window.BriwellApi.recordStatusTransition(payload));
  } catch (error) {
    showResult("manualSendResult", error.payload || { status: "mock_recorded", next_status: "dm_sent" });
  }
}

async function saveSnapshot() {
  const payload = {
    campaign_id: byId("snapshotCampaign").value.trim(),
    creator_id: byId("snapshotCreator").value.trim(),
    post_url: byId("snapshotPostUrl").value.trim(),
    coupon_code: byId("snapshotCoupon").value.trim(),
    view_count: Number(byId("snapshotViews").value || 0),
    revenue_usd: Number(byId("snapshotRevenue").value || 0),
    source_type: "manual",
    source_risk_level: "low",
  };
  try {
    showResult("snapshotResult", await window.BriwellApi.savePerformanceSnapshot(payload));
  } catch (error) {
    showResult("snapshotResult", error.payload || { status: "mock_saved", snapshot: payload });
  }
}

async function saveContract() {
  const payload = {
    creator_id: byId("contractCreator").value.trim(),
    campaign_id: byId("contractCampaign").value.trim(),
    deliverables: { videos: Number(byId("contractVideos").value || 1), usage_rights_days: 30 },
    compensation_terms: { fee_usd: Number(byId("contractFee").value || 0), sample: true },
  };
  try {
    showResult("contractResult", await window.BriwellApi.saveContract(payload));
  } catch (error) {
    showResult("contractResult", error.payload || { status: "mock_saved", contract: payload });
  }
}

function buildMockDiscoveryRows(countries, product, platform, limit) {
  const keywords = {
    MX: ["protectorsolar", "skincaremexico", "kbeautymexico", "rutinafacial"],
    PE: ["kbeautyperu", "protectorperu", "pielperu", "skincareperu"],
    EC: ["skincareecuador", "protectorsolecuador", "rutinaecuador", "kbeautyecuador"],
  };
  return countries.flatMap((country) =>
    (keywords[country] || []).slice(0, limit).map((keyword) => ({
      country,
      product_category: product,
      keyword,
      platform,
      source_type: "manual",
    }))
  );
}

function buildMockCoverageAudit(countries, product, limit) {
  const intents = ["discovery", "concern", "format", "commerce"];
  const selected = intents.slice(0, Math.max(1, Math.min(limit, intents.length)));
  const missing = intents.filter((intent) => !selected.includes(intent));
  return countries.map((country) => ({
    country,
    product_category: product,
    selected_count: Math.min(limit, 4),
    available_count: 4,
    selected_intent_types: selected,
    missing_intent_types: missing,
    false_negative_risks: missing.length
      ? [`Missing ${missing.map(formatIntent).join(", ")} queries can exclude valid niche creators.`]
      : ["Balanced intent coverage keeps discovery from overfitting to one creator archetype."],
    recommended_actions: missing.length
      ? ["Run second-pass expansion before excluding a market or product category."]
      : ["Keep nano, micro, and mid-tier creators through first-pass screening."],
  }));
}

function buildMockRecallSafeguards() {
  return [
    "하드 팔로워 컷오프 금지",
    "Discovery, Concern, Format, Commerce intent 균형 유지",
    "최종 제외 전 최근 20개 게시물 스크리닝",
    "TikTok, Instagram, 승인 provider, 수동 import를 별도 소스 레인으로 관리",
  ];
}

function renderDiscoveryRows(items) {
  byId("discoveryTable").innerHTML =
    items
      .map(
        (item) => `
      <tr>
        <td>${escapeHtml(formatMarket(item.country))}</td>
        <td>${escapeHtml(formatProductCategory(item.product_category || item.product || ""))}</td>
        <td>${escapeHtml(item.keyword || item.query || "")}</td>
        <td>${escapeHtml(formatPlatform(item.platform || ""))}</td>
        <td>${escapeHtml(formatSourceTypes([item.source_type || item.allowed_source_type || "manual"])[0])}</td>
      </tr>
    `
      )
      .join("") || emptyRow(5, "생성된 발굴 브리프 없음");
}

function bindCreatorOpenButtons() {
  document.querySelectorAll("[data-select-creator]").forEach((button) => {
    button.onclick = () => {
      const creator = state.creators.find((item) => item.creator_id === button.dataset.selectCreator);
      if (creator) {
        state.selectedCreatorId = creator.creator_id;
      }
      renderPriorityTable();
      renderPostCreatorSelect();
      renderPostImportTable();
      renderCandidateTable();
      renderCandidateDetail(creator);
      document.querySelector('[data-view="candidates"]').click();
    };
  });
}

function bindShortlistButtons() {
  document.querySelectorAll("[data-add-to-campaign]").forEach((button) => {
    button.onclick = () => {
      const creator = state.creators.find((item) => item.creator_id === button.dataset.addToCampaign);
      showToast(`@${creator?.username || "creator"} shortlisted for campaign review`);
    };
  });
}

function bindRecentScreenButtons() {
  document.querySelectorAll("[data-run-recent-screen]").forEach((button) => {
    button.onclick = () => {
      state.selectedCreatorId = button.dataset.runRecentScreen;
      renderPostCreatorSelect();
      runRecentScreenForCreator(button.dataset.runRecentScreen);
    };
  });
}

function normalizeApiCreator(creator) {
  return {
    creator_id: creator.creator_id || creator.id || stableCreatorId(creator.username || "creator"),
    username: creator.username || "creator",
    display_name: creator.display_name || creator.username || "Creator",
    country: normalizeCountry(creator.country),
    profile_url: creator.profile_url || "",
    bio: creator.bio || "",
    profile_image_url: creator.profile_image_url || creator.avatar_url || creator.thumbnail_url || fallbackProfileImage(creator),
    channel_image_url: creator.channel_image_url || creator.cover_image_url || fallbackChannelImage(creator),
    follower_count: toNumber(creator.follower_count),
    avg_views: toNumber(creator.avg_views || creator.average_views),
    engagement_rate: toNumber(creator.engagement_rate),
    platform: creator.platform || "tiktok",
    source_risk_level: creator.source_risk_level || "low",
    final_score: toNumber(creator.final_score || creator.score || 70),
    risk_penalty: toNumber(creator.risk_penalty || 5),
    segment: creator.segment || "review_creator",
    signals: creator.signals || creator.recommended_products || ["Profile"],
    recommended_products: creator.recommended_products || [],
    recommended_campaign_angle: creator.recommended_campaign_angle || "",
  };
}

function normalizeCsvCreator(row, index) {
  const username = String(row.username || row.handle || row.account || `creator_${index + 1}`).replace(/^@/, "").trim();
  return normalizeApiCreator({
    creator_id: row.creator_id || stableCreatorId(username),
    username,
    display_name: row.display_name || row.name || username,
    country: normalizeCountry(row.country || row.market),
    profile_url: row.profile_url || row.url || `https://example.com/@${username}`,
    bio: row.bio || "",
    follower_count: row.follower_count || row.followers || 0,
    avg_views: row.avg_views || row.average_views || 0,
    engagement_rate: row.engagement_rate || row.er || 0,
    platform: row.platform || "tiktok",
    source_risk_level: normalizeRisk(row.source_risk_level || row.risk || "low"),
    profile_image_url: row.profile_image_url || "",
    channel_image_url: row.channel_image_url || "",
    signals: splitList(row.signals || row.tags || "CSV Import"),
    recommended_products: splitList(row.recommended_products || row.product_categories || ""),
    recommended_campaign_angle: row.recommended_campaign_angle || "CSV import candidate pending recent 20 posts screen.",
  });
}

function normalizeCsvPost(row, creatorId, index) {
  const id = row.platform_video_id || row.video_id || `${creatorId}-post-${index + 1}`;
  return {
    creator_id: row.creator_id || creatorId,
    video_id: row.video_id || id,
    platform_video_id: id,
    url: row.url || row.post_url || `https://example.com/${creatorId}/post/${index + 1}`,
    caption: row.caption || row.text || "",
    transcript: row.transcript || "",
    hashtags: splitList(row.hashtags || row.tags || ""),
    posted_at: normalizeDate(row.posted_at || row.date),
    view_count: toNumber(row.view_count || row.views),
    like_count: toNumber(row.like_count || row.likes),
    comment_count: toNumber(row.comment_count || row.comments),
    share_count: toNumber(row.share_count || row.shares),
    save_count: toNumber(row.save_count || row.saves),
    duration_seconds: toNumber(row.duration_seconds || row.duration),
    thumbnail_url: row.thumbnail_url || "",
    source_url: row.source_url || row.url || row.post_url || "",
  };
}

function toCreatorImportItem(creator) {
  return {
    country: creator.country,
    username: creator.username,
    profile_url: creator.profile_url || `https://example.com/@${creator.username}`,
    display_name: creator.display_name || creator.username,
    bio: creator.bio || "",
    language: "es",
    follower_count: toNumber(creator.follower_count),
    source_url: creator.profile_url || "",
  };
}

function toVideoImportItem(post) {
  return {
    url: post.url,
    platform_video_id: post.platform_video_id || post.video_id,
    caption: post.caption || "",
    hashtags: post.hashtags || [],
    posted_at: post.posted_at || null,
    view_count: toNumber(post.view_count),
    like_count: toNumber(post.like_count),
    comment_count: toNumber(post.comment_count),
    share_count: toNumber(post.share_count),
    save_count: toNumber(post.save_count),
    duration_seconds: toNumber(post.duration_seconds),
    thumbnail_url: post.thumbnail_url || null,
    transcript: post.transcript || null,
    raw_metadata: { manual_import: true, source: "dashboard_talent_intake" },
    source_url: post.source_url || post.url,
  };
}

function toRecentPostSnapshot(post) {
  return {
    video_id: post.platform_video_id || post.video_id,
    url: post.url,
    caption: post.caption || "",
    transcript: post.transcript || "",
    hashtags: post.hashtags || [],
    posted_at: post.posted_at || null,
    view_count: toNumber(post.view_count),
    like_count: toNumber(post.like_count),
    comment_count: toNumber(post.comment_count),
    share_count: toNumber(post.share_count),
    save_count: toNumber(post.save_count),
    duration_seconds: toNumber(post.duration_seconds),
    thumbnail_url: post.thumbnail_url || null,
  };
}

function creatorSnapshot(creator) {
  return {
    creator_id: creator.creator_id,
    country: creator.country,
    username: creator.username,
    display_name: creator.display_name,
    profile_url: creator.profile_url,
    profile_image_url: creator.profile_image_url,
    channel_image_url: creator.channel_image_url,
    source_risk_level: creator.source_risk_level,
    follower_count: creator.follower_count,
    avg_views: creator.avg_views,
    engagement_rate: creator.engagement_rate,
    platform: creator.platform,
    final_score: creator.final_score,
    risk_penalty: creator.risk_penalty,
    segment: creator.segment,
    recommended_products: creator.recommended_products || [],
  };
}

function extractRecentScreenOutput(payload) {
  if (!payload) return null;
  if (payload.result?.output) return payload.result.output;
  if (payload.output) return payload.output;
  if (payload.suitability_decision || payload.suitability_score) return payload;
  return null;
}

function applyScreenResultToCreator(creatorId, output) {
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  if (!creator || !output) return;
  const score = Math.round(Number(output.suitability_score || 0));
  if (score > 0) creator.final_score = Math.max(Number(creator.final_score || 0), score);
  creator.recommended_products = unique([
    ...(creator.recommended_products || []),
    ...(output.matched_product_categories || []),
  ]);
  creator.signals = unique([
    ...(creator.signals || []),
    decisionLabel(output.suitability_decision),
    ...formatProductList(output.matched_product_categories),
  ]).filter(Boolean).slice(0, 5);
}

function buildNoPostsScreenResult() {
  return {
    post_count_analyzed: 0,
    expected_post_count: 20,
    suitability_decision: "human_review",
    suitability_score: 0,
    matched_product_categories: [],
    coverage_gaps: ["recent_posts_missing", "transcripts_missing", "public_metrics_missing"],
    risk_notes: [],
    next_step: "collect_recent_20_posts",
    missing_data: ["recent_posts"],
    recent_post_observations: ["No approved recent post inputs are loaded for this candidate."],
  };
}

function mockRecentPostsScreen(creator, posts) {
  const text = posts
    .map((post) => `${post.caption || ""} ${post.transcript || ""} ${(post.hashtags || []).join(" ")}`)
    .join(" ")
    .toLowerCase();
  const postCount = posts.length;
  const beautyHits = countMatchingPosts(posts, ["skincare", "piel", "belleza", "rutina", "spf", "protector", "serum", "limpiador", "maquillaje"]);
  const kbeautyHits = countMatchingPosts(posts, ["kbeauty", "k-beauty", "coreano", "coreana", "korean"]);
  const commerceHits = countMatchingPosts(posts, ["link", "codigo", "código", "descuento", "comprar", "precio", "tienda"]);
  const riskNotes = ["cura", "dermatitis", "melasma", "resultado garantizado"].filter((term) => text.includes(term));
  const matched = productMatches(text);
  const beautyRatio = postCount ? beautyHits / postCount : 0;
  const kbeautyRatio = postCount ? kbeautyHits / postCount : 0;
  const commerceRatio = postCount ? commerceHits / postCount : 0;
  const coverageGaps = [];
  if (postCount < 20) coverageGaps.push("recent_posts_below_20");
  if (!posts.some((post) => post.transcript)) coverageGaps.push("transcripts_missing");
  if (!matched.length) coverageGaps.push("product_category_signal_missing");
  if (!commerceHits) coverageGaps.push("commerce_intent_signal_missing");

  const brandSafety = riskNotes.length ? 52 : 88;
  const score = Math.round(
    Math.min(100, beautyRatio * 34 + kbeautyRatio * 16 + commerceRatio * 18 + brandSafety * 0.22 + Math.min(postCount, 20) * 0.5)
  );
  let decision = "recheck_later";
  let nextStep = "do_not_prioritize";
  if (riskNotes.length >= 2) {
    decision = "avoid";
    nextStep = "exclude_until_operator_review";
  } else if (riskNotes.length || postCount < 20 || (score >= 50 && score < 75)) {
    decision = "human_review";
    nextStep = postCount < 20 ? "collect_more_recent_posts" : "operator_review";
  } else if (score >= 75) {
    decision = "pass_to_full_analysis";
    nextStep = "run_full_profile_comment_multimodal_analysis";
  }

  return {
    status: "ok",
    post_count_analyzed: postCount,
    expected_post_count: 20,
    suitability_decision: decision,
    suitability_score: score,
    beauty_content_ratio: Number(beautyRatio.toFixed(3)),
    kbeauty_signal_ratio: Number(kbeautyRatio.toFixed(3)),
    skincare_relevance_score: Math.round(beautyRatio * 100),
    commerce_signal_score: Math.round(commerceRatio * 100),
    consistency_score: Math.min(100, 45 + postCount * 2),
    brand_safety_precheck_score: brandSafety,
    matched_product_categories: matched,
    recent_post_observations: [
      `${postCount} approved recent posts analyzed for @${creator.username}.`,
      "Use this screen before spending multimodal analysis budget.",
    ],
    coverage_gaps: coverageGaps,
    risk_notes: riskNotes,
    next_step: nextStep,
    missing_data: coverageGaps,
    confidence: postCount >= 20 && !coverageGaps.length ? 0.78 : 0.58,
  };
}

function renderScreenCompact(result) {
  return `
    <div class="screen-compact">
      <div class="screen-compact-head">
        <span class="decision-pill ${decisionClass(result.suitability_decision)}">${escapeHtml(decisionLabel(result.suitability_decision))}</span>
        <strong>${escapeHtml(String(Math.round(Number(result.suitability_score || 0))))}</strong>
      </div>
      <div class="policy-line"><span>Products</span><strong>${escapeHtml(formatProductList(result.matched_product_categories).join(", ") || "Needs data")}</strong></div>
      <div class="policy-line"><span>Missing Data</span><strong>${escapeHtml((result.coverage_gaps || result.missing_data || []).slice(0, 2).join(", ") || "None")}</strong></div>
    </div>
  `;
}

function renderScreenPlaceholder(creatorId) {
  const count = (state.recentPostsByCreator[creatorId] || []).length;
  return `
    <div class="screen-compact">
      <div class="screen-compact-head">
        <span class="decision-pill decision-review">Not Screened</span>
        <strong>${escapeHtml(String(count))}/20</strong>
      </div>
      <div class="policy-line"><span>Next</span><strong>Run Recent 20 Posts Screen</strong></div>
    </div>
  `;
}

function renderScreenFull(result, creator, postCount) {
  const gaps = result.coverage_gaps || result.missing_data || [];
  return `
    <div class="screening-grid">
      <article class="screening-card score-card">
        <span>Suitability Score</span>
        <strong>${escapeHtml(String(Math.round(Number(result.suitability_score || 0))))}</strong>
        <small>${creator ? `@${escapeHtml(creator.username)}` : "Candidate"} · ${escapeHtml(postCount)} / 20 posts</small>
      </article>
      <article class="screening-card">
        <span>Decision</span>
        <strong><span class="decision-pill ${decisionClass(result.suitability_decision)}">${escapeHtml(decisionLabel(result.suitability_decision))}</span></strong>
        <small>${escapeHtml(result.next_step || "operator_review")}</small>
      </article>
      <article class="screening-card">
        <span>Product Match</span>
        <strong>${escapeHtml(formatProductList(result.matched_product_categories).join(", ") || "Needs Data")}</strong>
        <small>${escapeHtml(formatPercent(Number(result.kbeauty_signal_ratio || 0) * 100))} K-Beauty signal</small>
      </article>
      <article class="screening-card">
        <span>Missing Data</span>
        <strong>${escapeHtml(String(gaps.length))}</strong>
        <small>${escapeHtml(gaps.slice(0, 3).join(", ") || "None")}</small>
      </article>
    </div>
    <div class="screening-notes">
      <div>
        <h3>Risk Notes</h3>
        <p>${escapeHtml((result.risk_notes || []).join(", ") || "No precheck risk notes")}</p>
      </div>
      <div>
        <h3>Next Action</h3>
        <p>${escapeHtml(formatNextStep(result.next_step))}</p>
      </div>
      <div>
        <h3>Observations</h3>
        <p>${escapeHtml((result.recent_post_observations || []).join(" "))}</p>
      </div>
    </div>
  `;
}

async function readFileInput(id) {
  const input = byId(id);
  const file = input.files?.[0];
  if (!file) throw new Error("CSV file is required.");
  return file.text();
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      field += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }
    field += char;
  }
  row.push(field);
  rows.push(row);

  const cleanRows = rows.filter((items) => items.some((item) => String(item).trim() !== ""));
  if (!cleanRows.length) return [];
  const headers = cleanRows[0].map((header) => normalizeHeader(header));
  return cleanRows.slice(1).map((items) => {
    const object = {};
    headers.forEach((header, index) => {
      object[header] = String(items[index] || "").trim();
    });
    return object;
  });
}

function parseManualPosts(text) {
  if (!text) return [];
  const firstLine = text.split(/\r?\n/)[0].toLowerCase();
  if (firstLine.includes("url") || firstLine.includes("caption") || firstLine.includes("view_count")) {
    return parseCsv(text);
  }
  const headers = ["url", "caption", "hashtags", "view_count", "like_count", "comment_count"];
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line) => {
      const values = parseCsv(`${headers.join(",")}\n${line}`)[0] || {};
      return values;
    });
}

function buildSeedPosts(creatorId, product, count) {
  const productCopy = {
    sunscreen: {
      caption: "Rutina skincare con protector solar coreano SPF y link de compra.",
      transcript: "Este protector solar coreano se siente ligero en la piel y funciona bien para uso diario.",
      hashtags: ["skincare", "kbeauty", "protectorsolar"],
    },
    calming_serum: {
      caption: "Serum coreano para barrera de la piel sensible, textura ligera y rutina de noche.",
      transcript: "La fórmula se siente calmante y ayuda a que la rutina sea cómoda.",
      hashtags: ["skincare", "kbeauty", "serum"],
    },
    cleanser: {
      caption: "Limpieza facial coreana para rutina diaria, textura suave y buen acabado.",
      transcript: "Uso el limpiador en doble limpieza y me gusta para contenido UGC.",
      hashtags: ["skincare", "kbeauty", "limpiador"],
    },
  };
  const template = productCopy[product] || productCopy.sunscreen;
  return Array.from({ length: count }, (_, index) => ({
    creator_id: creatorId,
    video_id: `${creatorId}-seed-${index + 1}`,
    platform_video_id: `${creatorId}-seed-${index + 1}`,
    url: `https://example.com/${creatorId}/video/${index + 1}`,
    caption: template.caption,
    transcript: index % 3 === 0 ? "" : template.transcript,
    hashtags: template.hashtags,
    posted_at: new Date(Date.now() - index * 86400000).toISOString(),
    view_count: 9000 + index * 420,
    like_count: 580 + index * 17,
    comment_count: 42 + index,
    share_count: 18 + index,
    save_count: 24 + index,
    duration_seconds: 38 + (index % 12),
  }));
}

function countMatchingPosts(posts, terms) {
  return posts.filter((post) => {
    const text = `${post.caption || ""} ${post.transcript || ""} ${(post.hashtags || []).join(" ")}`.toLowerCase();
    return terms.some((term) => text.includes(term));
  }).length;
}

function productMatches(text) {
  const products = {
    sunscreen: ["spf", "protector", "bloqueador", "solar"],
    calming_serum: ["serum", "calmante", "barrera", "rojeces"],
    cleanser: ["limpiador", "limpieza", "cleanser"],
    sheet_mask: ["mascarilla", "mask"],
    cushion_foundation: ["cushion", "base", "maquillaje"],
  };
  return Object.entries(products)
    .filter(([, terms]) => terms.some((term) => text.includes(term)))
    .map(([product]) => product);
}

function talentCell(creator) {
  return `
    <div class="talent-cell">
      ${avatarImage(creator, "profile-avatar")}
      <div class="talent-copy">
        <strong>@${escapeHtml(creator.username)}</strong>
        <span>${escapeHtml(creator.display_name || "")}</span>
        <small>${escapeHtml(formatPlatform(creator.platform || ""))} · ${escapeHtml(formatSegment(creator.segment || "review_creator"))}</small>
      </div>
    </div>
  `;
}

function audienceCell(creator) {
  return `
    <div class="audience-cell">
      <strong>${escapeHtml(formatCompactNumber(creator.follower_count))}</strong>
      <span>${escapeHtml(formatCompactNumber(creator.avg_views))} avg views</span>
      <span>${escapeHtml(formatPercent(creator.engagement_rate))} engagement</span>
    </div>
  `;
}

function avatarImage(creator, className) {
  const image = profileImage(creator);
  const label = creator?.display_name || creator?.username || "Creator";
  return `<img class="${escapeHtml(className)}" src="${escapeHtml(image)}" alt="${escapeHtml(label)} profile image">`;
}

function profileImage(creator) {
  return creator?.profile_image_url || fallbackProfileImage(creator || {});
}

function channelImage(creator) {
  return creator?.channel_image_url || fallbackChannelImage(creator || {});
}

function fallbackProfileImage(creator) {
  const username = String(creator.username || "").toLowerCase();
  if (username.includes("andrea")) return "./assets/creator-andrea.svg";
  if (username.includes("rutina")) return "./assets/creator-rutina.svg";
  return "./assets/creator-luz.svg";
}

function fallbackChannelImage(creator) {
  const username = String(creator.username || "").toLowerCase();
  if (username.includes("andrea")) return "./assets/channel-andrea.svg";
  if (username.includes("rutina")) return "./assets/channel-rutina.svg";
  return "./assets/channel-luz.svg";
}

function findCreatorForReview(item) {
  return state.creators.find((creator) => creator.creator_id === item.creator_id || creator.username === item.creator);
}

function filteredCreators() {
  if (state.activeCountry === "ALL") return state.creators;
  return state.creators.filter((creator) => creator.country === state.activeCountry);
}

function scoreCell(score) {
  const value = Number(score || 0);
  return `
    <div class="score-wrap">
      <strong>${escapeHtml(String(value))}</strong>
      <div class="score-bar"><span style="width:${Math.max(0, Math.min(100, value))}%"></span></div>
    </div>
  `;
}

function riskBadge(level) {
  const normalized = String(level || "low").toLowerCase();
  if (normalized === "low") return '<span class="badge green">Low</span>';
  if (normalized === "low_medium") return '<span class="badge amber">Low/Medium</span>';
  if (normalized === "medium") return '<span class="badge amber">Medium</span>';
  return '<span class="badge red">Blocked</span>';
}

function signalTags(signals) {
  return (signals || [])
    .filter(Boolean)
    .slice(0, 4)
    .map((signal) => `<span class="badge teal">${escapeHtml(signal)}</span>`)
    .join(" ");
}

function mergeCreators(current, incoming) {
  const map = new Map(current.map((creator) => [creator.creator_id, creator]));
  incoming.forEach((creator) => {
    const previous = map.get(creator.creator_id) || {};
    map.set(creator.creator_id, { ...previous, ...creator });
  });
  return Array.from(map.values());
}

function highestRiskLevel(creators) {
  const levels = creators.map((creator) => normalizeRisk(creator.source_risk_level));
  if (levels.includes("medium")) return "medium";
  if (levels.includes("low_medium")) return "low_medium";
  return "low";
}

function sourceRiskForCreator(creatorId) {
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  return normalizeRisk(creator?.source_risk_level || "low");
}

function normalizeRisk(value) {
  const normalized = String(value || "low").trim().toLowerCase().replace("-", "_");
  if (["low", "low_medium", "medium"].includes(normalized)) return normalized;
  if (normalized === "low/medium") return "low_medium";
  return "low";
}

function normalizeCountry(value) {
  const normalized = String(value || "MX").trim().toUpperCase();
  if (["MX", "MEXICO", "MÉXICO"].includes(normalized)) return "MX";
  if (["PE", "PERU", "PERÚ"].includes(normalized)) return "PE";
  if (["EC", "ECUADOR"].includes(normalized)) return "EC";
  return "MX";
}

function normalizeHeader(value) {
  return String(value || "")
    .trim()
    .replace(/^\uFEFF/, "")
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function stableCreatorId(username) {
  return `creator-${String(username || "candidate").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "candidate"}`;
}

function splitList(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value || "")
    .split(/[|;,]/)
    .map((item) => item.trim().replace(/^#/, ""))
    .filter(Boolean);
}

function normalizeDate(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function toNumber(value) {
  const normalized = String(value ?? "").replace(/,/g, "").trim();
  if (!normalized) return 0;
  const number = Number(normalized);
  return Number.isFinite(number) ? number : 0;
}

function unique(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function formatSegment(segment) {
  const labels = {
    review_creator: "Review Creator",
    beauty_educator: "Beauty Educator",
    ugc_creator: "UGC Producer",
    viral_micro: "Viral Micro",
    commerce_creator: "Commerce Creator",
    brand_builder: "Brand Builder",
    avoid: "Do Not Use",
  };
  return labels[segment] || segment;
}

function formatSourceTypes(types) {
  const labels = {
    manual: "Manual Import",
    official_api: "Official API",
    approved_provider: "Approved Provider",
    creator_provided: "Creator Provided",
    browser_automation: "Browser Automation",
    captcha_bypass: "CAPTCHA Bypass",
    public_page_scrape: "Public Page Scrape",
  };
  return (types || []).map((type) => labels[type] || type);
}

function formatMarket(country) {
  const labels = {
    MX: "Mexico",
    PE: "Peru",
    EC: "Ecuador",
  };
  return labels[country] || country || "";
}

function formatProductCategory(category) {
  const labels = {
    sunscreen: "Sunscreen",
    calming_serum: "Calming Serum",
    cleanser: "Cleanser",
    sheet_mask: "Sheet Mask",
    cushion_foundation: "Cushion Foundation",
  };
  return labels[category] || category;
}

function formatProductList(products) {
  return (products || []).map(formatProductCategory);
}

function formatPlatform(platform) {
  const labels = {
    tiktok: "TikTok",
    instagram: "Instagram",
  };
  return labels[platform] || platform;
}

function formatBoolean(value) {
  return value ? "Enabled" : "Disabled";
}

function formatReadiness(status) {
  const labels = {
    ok: "Ready",
    blocked: "Blocked",
    ready_with_warnings: "Warnings",
    unknown: "Unknown",
  };
  return labels[status] || status || "Unknown";
}

function formatPolicyText(policy) {
  if (!policy) return "Only compliant acquisition paths are allowed for candidate analysis.";
  if (policy.includes("Unauthorized scraping")) {
    return "Unauthorized scraping is blocked. Use manual import, official APIs, approved providers, or creator-provided data only.";
  }
  return policy;
}

function formatProvider(provider) {
  const labels = {
    google: "Google Gemini",
  };
  return labels[provider] || provider;
}

function formatAdapter(adapter) {
  const labels = {
    GeminiTextAdapter: "Gemini Text Adapter",
  };
  return labels[adapter] || adapter;
}

function formatIntent(value) {
  const labels = {
    discovery: "Discovery",
    concern: "Concern",
    format: "Format",
    commerce: "Commerce",
  };
  return labels[value] || value;
}

function decisionLabel(decision) {
  const labels = {
    pass_to_full_analysis: "Pass",
    pass: "Pass",
    human_review: "Human Review",
    recheck_later: "Recheck Later",
    avoid: "Avoid",
  };
  return labels[decision] || "Human Review";
}

function decisionClass(decision) {
  if (decision === "pass_to_full_analysis" || decision === "pass") return "decision-pass";
  if (decision === "recheck_later") return "decision-recheck";
  if (decision === "avoid") return "decision-avoid";
  return "decision-review";
}

function formatNextStep(value) {
  const labels = {
    run_full_profile_comment_multimodal_analysis: "Profile, comment, multimodal full analysis 실행",
    collect_more_recent_posts: "최근 게시물 20개까지 추가 수집",
    operator_review: "운영자 검수 후 다음 단계 결정",
    do_not_prioritize: "현재 캠페인 우선순위에서 제외 후 추후 재검토",
    collect_recent_20_posts: "승인된 소스에서 최근 게시물 20개 입력",
    exclude_until_operator_review: "운영자 리스크 검수 전 제외",
  };
  return labels[value] || value || "운영자 검수";
}

function setApiStatus(status, label) {
  const dot = byId("apiDot");
  dot.classList.remove("online", "offline");
  if (status === "online") dot.classList.add("online");
  if (status === "offline") dot.classList.add("offline");
  byId("apiStatus").textContent = label;
}

function showResult(id, payload) {
  const box = byId(id);
  box.classList.add("active");
  box.textContent = JSON.stringify(payload, null, 2);
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.add("active");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("active"), 2400);
}

function emptyRow(colspan, message) {
  return `<tr><td colspan="${colspan}" class="muted">${escapeHtml(message)}</td></tr>`;
}

function truncate(value, max) {
  const text = String(value || "");
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function formatCurrencyCompact(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value || 0));
}

function formatCompactNumber(value) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatPercent(value) {
  const numeric = Number(value || 0);
  return `${numeric.toFixed(numeric % 1 === 0 ? 0 : 1)}%`;
}

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
