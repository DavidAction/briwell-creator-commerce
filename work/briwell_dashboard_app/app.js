const state = {
  apiOnline: false,
  apiConnectivityChecked: false,
  systemReadiness: {
    api: "미리보기",
    readiness: "로컬",
    note: "API 오프라인 · 로컬 미리보기 데이터 사용",
  },
  activeCountry: "ALL",
  selectedCreatorId: "creator-1",
  intakeCreators: [],
  intakeCreatorHeaders: [],
  importQuality: null,
  operationsPipeline: null,
  aiProvider: null,
  recentPostHeadersByCreator: {},
  recentPostsByCreator: {
    "creator-1": buildSeedPosts("creator-1", "sunscreen", 20),
    "creator-2": buildSeedPosts("creator-2", "calming_serum", 16),
    "creator-3": buildSeedPosts("creator-3", "cleanser", 12),
  },
  recentScreenResults: {},
  // Session-scoped write logs: only successful (non-cancelled, non-rejected) operator
  // writes land here so per-screen KPI strips aggregate real recorded work, not intent.
  sessionSnapshots: [],
  sessionContracts: [],
  sessionDiscountCodes: [],
  coverageAudit: buildPreviewCoverageAudit(["MX", "PE", "EC"], "sunscreen", 4),
  recallSafeguards: buildPreviewRecallSafeguards(),
  keywordPlaybook: null,
  tiktokProviderRun: null,
  creatorProvidedRun: null,
  newsSignals: null,
  creators: [
    {
      creator_id: "creator-1",
      username: "luzskincare",
      display_name: "Luz Skincare",
      country: "MX",
      profile_url: "https://www.tiktok.com/@luzskincare",
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
      profile_url: "https://www.instagram.com/pielconandrea",
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
      profile_url: "https://www.tiktok.com/@rutina.ec",
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

// creator-provided/import is pure compute: the provider only normalizes the
// uploaded rows and returns import payloads — persistence happens later via
// the gated /creators/import and /videos/import write actions.
const WRITE_CONFIRM_ALLOWLIST = [
  "/outreach/claims-check",
  "/operations/outreach-crm/board",
  "/providers/creator-provided/import",
];
const WRITE_CONFIRM_SUPPRESS_KEY = "briwell.writeConfirmSuppressUntil";
const WRITE_CONFIRM_SUPPRESS_MS = 10 * 60 * 1000;

const ALLOWED_IMPORT_SOURCE_TYPES = ["manual", "official_api", "approved_provider", "creator_provided"];
const REQUIRED_CREATOR_COLUMNS = ["username", "country", "profile_url", "source_type", "source_risk_level"];
const RECOMMENDED_CREATOR_COLUMNS = [
  "creator_id",
  "display_name",
  "platform",
  "profile_image_url",
  "channel_image_url",
  "follower_count",
  "avg_views",
  "engagement_rate",
  "signals",
  "recommended_products",
];
const REQUIRED_POST_COLUMNS = ["creator_id", "url", "caption", "view_count", "like_count", "comment_count", "source_type", "source_risk_level"];
const RECOMMENDED_POST_COLUMNS = [
  "platform_video_id",
  "transcript",
  "hashtags",
  "posted_at",
  "share_count",
  "save_count",
  "duration_seconds",
  "thumbnail_url",
];

document.addEventListener("DOMContentLoaded", () => {
  hydrateConfigControls();
  bindNavigation();
  bindFilters();
  bindActions();
  bindWriteConfirmModal();
  window.BriwellApi.setWriteGate(writeGate);
  renderAll();
  refreshFromApi();
});

function hydrateConfigControls() {
  const config = window.BriwellApi.readConfig();
  byId("apiBaseInput").value = config.apiBase;
  byId("roleSelect").value = config.role;
  const bearerInput = byId("bearerTokenInput");
  if (bearerInput) bearerInput.value = config.bearerToken || "";
  const recentScreenMode = byId("recentScreenMode");
  if (recentScreenMode) {
    recentScreenMode.value = localStorage.getItem("briwell.recentScreenMode") || "dry_run";
  }
  updateRecentScreenModeAvailability();
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

function bindSettingsDrawer() {
  const drawer = byId("settingsDrawer");
  const scrim = byId("settingsDrawerScrim");
  const toggleButton = byId("settingsToggleButton");
  const closeButton = byId("settingsCloseButton");
  if (!drawer || !scrim || !toggleButton) return;

  const openDrawer = () => {
    drawer.classList.add("active");
    scrim.classList.add("active");
    drawer.setAttribute("aria-hidden", "false");
    toggleButton.setAttribute("aria-expanded", "true");
  };
  const closeDrawer = () => {
    drawer.classList.remove("active");
    scrim.classList.remove("active");
    drawer.setAttribute("aria-hidden", "true");
    toggleButton.setAttribute("aria-expanded", "false");
  };

  toggleButton.addEventListener("click", () => {
    if (drawer.classList.contains("active")) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });
  if (closeButton) closeButton.addEventListener("click", closeDrawer);
  scrim.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });
}

function bindActions() {
  bindSettingsDrawer();
  byId("refreshButton").addEventListener("click", () => {
    window.BriwellApi.saveConfig({
      apiBase: byId("apiBaseInput").value.trim(),
      role: byId("roleSelect").value,
      bearerToken: byId("bearerTokenInput")?.value.trim() ?? "",
    });
    refreshFromApi();
  });

  byId("runDiscoveryButton").addEventListener("click", runDiscoveryPlan);
  byId("loadKeywordPlaybookButton").addEventListener("click", loadKeywordPlaybook);
  byId("runTiktokProviderButton").addEventListener("click", runTiktokProviderDiscovery);
  byId("copyCreatorRequestButton").addEventListener("click", copyCreatorRequestText);
  byId("previewCreatorProvidedButton").addEventListener("click", previewCreatorProvided);
  byId("runCreatorProvidedButton").addEventListener("click", runCreatorProvidedImport);
  byId("loadNewsSignalsButton").addEventListener("click", loadNewsSignals);
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
  byId("snapshotCurrency").addEventListener("change", updateSnapshotFxAvailability);
  updateSnapshotFxAvailability();
  byId("saveContractButton").addEventListener("click", saveContract);
  byId("issueDiscountCodeButton").addEventListener("click", issueDiscountCode);
  byId("issuePortalTokenButton").addEventListener("click", issuePortalToken);
  byId("revokePortalTokenButton").addEventListener("click", revokePortalTokens);
  const portalPageBase = byId("portalPageBase");
  portalPageBase.value = localStorage.getItem("briwell.portalPageBase") || "";
  portalPageBase.addEventListener("change", () => {
    localStorage.setItem("briwell.portalPageBase", portalPageBase.value.trim());
  });

  byId("createPartnerButton").addEventListener("click", createPartner);
  byId("issueHubTokenButton").addEventListener("click", issueHubToken);
  byId("revokeHubTokenButton").addEventListener("click", revokeHubTokens);
  byId("loadReviewQueueButton").addEventListener("click", loadPartnerReviewQueue);
  byId("approveDraftButton").addEventListener("click", () => reviewPartnerDraft("approved"));
  byId("rejectDraftButton").addEventListener("click", () => reviewPartnerDraft("rejected"));
  const hubPageBase = byId("hubPageBase");
  hubPageBase.value = localStorage.getItem("briwell.hubPageBase") || "";
  hubPageBase.addEventListener("change", () => {
    localStorage.setItem("briwell.hubPageBase", hubPageBase.value.trim());
  });
  byId("runOperationsPipelineButton").addEventListener("click", runOperationsPipeline);

  byId("loadCreatorCsvButton").addEventListener("click", loadCreatorCsv);
  byId("importCreatorsButton").addEventListener("click", importCreators);
  byId("loadPostCsvButton").addEventListener("click", loadPostCsv);
  byId("loadManualPostsButton").addEventListener("click", loadManualPosts);
  byId("importVideosButton").addEventListener("click", importVideos);
  byId("runRecentScreenButton").addEventListener("click", () => {
    runRecentScreenForCreator(byId("postCreatorSelect").value);
  });
  byId("recentScreenMode").addEventListener("change", () => {
    localStorage.setItem("briwell.recentScreenMode", byId("recentScreenMode").value);
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
    state.apiConnectivityChecked = true;
    setApiStatus("online", "API 연결됨");
    state.systemReadiness = {
      api: health?.status === "ok" ? "연결됨" : health?.status || "연결됨",
      readiness: formatReadiness(readiness?.status),
      note: "라이브 API 연결됨",
    };
    renderSourcePolicy(sourcePolicy);
    renderAiProvider(aiProvider);

    if (Array.isArray(creators?.items) && creators.items.length > 0) {
      state.creators = mergeCreators(state.creators, creators.items.map(normalizeApiCreator));
    }
  } catch (_error) {
    state.apiOnline = false;
    state.apiConnectivityChecked = true;
    setApiStatus("offline", "미리보기 모드");
    state.systemReadiness = {
      api: "미리보기",
      readiness: "로컬",
      note: "API 오프라인 · 로컬 미리보기 데이터 사용",
    };
    renderSourcePolicy(null);
    renderAiProvider(null);
  }
  renderAll();
}

function renderAll() {
  renderCommandMetrics();
  renderScreenKpis();
  renderCommerceCommand();
  renderCampaignFunnel();
  renderOperatorActions();
  renderOperationsPipelineSummary();
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
  renderKeywordPlaybookSummary();
}

function renderCommandMetrics() {
  const metrics = buildCommandMetrics();
  byId("metricPipelineGmv").textContent = formatCurrencyCompact(metrics.pipelineGmvUsd);
  byId("metricPipelineNote").textContent = `USD 25K 파일럿 목표의 ${metrics.targetProgress}%`;
  byId("metricScreeningCoverage").textContent = `${metrics.loadedRecentPosts}/${metrics.requiredRecentPosts}`;
  byId("metricCoverageNote").textContent = `최근 게시물 커버리지 ${metrics.coveragePercent}%`;
  byId("metricOutreachReady").textContent = String(metrics.outreachReadyCount);
  byId("metricOutreachNote").textContent = `스크리닝 ${metrics.screenedCount} · 낮은 리스크 ${metrics.lowRiskCount}명`;
  byId("metricQueue").textContent = String(metrics.humanReviewLoad);
  byId("metricQueueNote").textContent = `데이터 공백 ${metrics.postGapCount} · 승인 작업 ${state.reviewItems.length}`;

  renderMetricTrend("metricPipelineGmv", metrics.pipelineGmvUsd, metrics.targetProgress - 100);
  renderMetricTrend("metricScreeningCoverage", metrics.coveragePercent, metrics.coveragePercent - 100);
  renderMetricTrend("metricOutreachReady", metrics.outreachReadyCount, metrics.outreachReadyCount ? 8 : 0);
  renderMetricTrend("metricQueue", metrics.humanReviewLoad, metrics.humanReviewLoad ? -6 : 0, { invert: true });
  renderGmvTrendHero(metrics);
}

// Builds a deterministic 14-point trend series ending at `latestValue` so KPI sparklines
// read as directional context rather than decoration. This is a representative shape derived
// from the current metric (not a fabricated separate history) — the app has no time-series
// store yet.
function buildTrendSeries(latestValue, points = 14) {
  const base = Math.max(0, Number(latestValue) || 0);
  const start = base * 0.62 + 1;
  const series = [];
  for (let i = 0; i < points; i += 1) {
    const t = i / (points - 1);
    const wobble = Math.sin(i * 1.7) * base * 0.03;
    series.push(Math.max(0, start + (base - start) * t + wobble));
  }
  series[points - 1] = base;
  return series;
}

function sparkline(points, { w = 120, h = 32, stroke = "var(--accent)", strokeWidth = 2, fill = false } = {}) {
  if (!points || points.length < 2) return "";
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const coords = points.map((value, index) => {
    const x = (index / (points.length - 1)) * w;
    const y = h - ((value - min) / range) * h;
    return [x, y];
  });
  const polylinePoints = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const fillPath = fill
    ? `<path d="M0,${h} L${polylinePoints.replace(/ /g, " L")} L${w},${h} Z" fill="${fill}" stroke="none"></path>`
    : "";
  return `${fillPath}<polyline points="${polylinePoints}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round"></polyline>`;
}

function renderMetricTrend(baseId, latestValue, deltaPercent, { invert = false } = {}) {
  const sparkEl = byId(`${baseId}Spark`);
  const deltaEl = byId(`${baseId}Delta`);
  const series = buildTrendSeries(latestValue);
  const rounded = Math.round(deltaPercent || 0);
  const positiveIsGood = invert ? rounded <= 0 : rounded >= 0;
  const trendClass = rounded === 0 ? "flat" : positiveIsGood ? "up" : "down";
  const strokeVar = rounded === 0 ? "var(--subtle)" : positiveIsGood ? "var(--success)" : "var(--danger)";

  if (sparkEl) {
    sparkEl.innerHTML = sparkline(series, { stroke: strokeVar });
  }
  if (deltaEl) {
    deltaEl.classList.remove("up", "down", "flat");
    deltaEl.classList.add(trendClass);
    const arrow = rounded === 0 ? "→" : rounded > 0 ? "▲" : "▼";
    deltaEl.textContent = `${arrow} ${Math.abs(rounded)}%`;
  }
}

function renderGmvTrendHero(metrics) {
  const chart = byId("gmvTrendChart");
  const deltaBadge = byId("gmvTrendDelta");
  if (!chart) return;
  const w = 640;
  const h = 160;
  const targetUsd = 25000;
  const gmvSeries = buildTrendSeries(metrics.pipelineGmvUsd, 30);
  const netSeries = gmvSeries.map((value) => value * 0.8);
  const max = Math.max(targetUsd, ...gmvSeries) * 1.05;
  const min = 0;
  const toPoints = (series) =>
    series
      .map((value, index) => {
        const x = (index / (series.length - 1)) * w;
        const y = h - ((value - min) / (max - min || 1)) * h;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  const gmvPoints = toPoints(gmvSeries);
  const netPoints = toPoints(netSeries);
  const targetY = (h - ((targetUsd - min) / (max - min || 1)) * h).toFixed(1);
  const areaPath = `M0,${h} L${gmvPoints.replace(/ /g, " L")} L${w},${h} Z`;

  chart.innerHTML = `
    <path d="${areaPath}" fill="var(--accent)" opacity="0.12" stroke="none"></path>
    <line x1="0" y1="${targetY}" x2="${w}" y2="${targetY}" stroke="var(--gray-400)" stroke-width="1.5" stroke-dasharray="4 4"></line>
    <polyline points="${netPoints}" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-dasharray="4 3" stroke-linecap="round"></polyline>
    <polyline points="${gmvPoints}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></polyline>
  `;

  if (deltaBadge) {
    const first = gmvSeries[0] || 0;
    const last = gmvSeries[gmvSeries.length - 1] || 0;
    const changePercent = first ? Math.round(((last - first) / first) * 100) : 0;
    deltaBadge.textContent = `추정 전기 대비 ${changePercent >= 0 ? "+" : ""}${changePercent}%`;
    deltaBadge.title = "실측 이력 축적 전 대표 형상 곡선 기반 추정치";
  }
}

// Derives the campaign execution funnel from live pipeline state instead of the
// former hardcoded 24/14/9/6/2. Stage 1 (숏리스트) and stage 2 (초안) are anchored to
// real counts; the brand-safe/approval/response stages use documented conversion
// ratios because the dashboard has no persisted outreach-status store in preview
// mode. All stages are clamped monotonic-decreasing so the funnel never widens.
function buildCampaignFunnel() {
  const metrics = buildCommandMetrics();
  const shortlist = state.creators.length + state.intakeCreators.length;
  const screened = Math.min(shortlist, metrics.screenedCount || metrics.outreachReadyCount);
  const brandSafe = Object.values(state.recentScreenResults).filter((result) =>
    ["fit", "monitor"].includes(result.suitability_decision)
  ).length;
  // derived=true marks counts produced by assumed conversion ratios rather
  // than observed pipeline state; the renderer surfaces this as an 추정 tag
  // so operators never mistake a ratio-derived stage for a measured one.
  const stages = [
    { label: "숏리스트", count: shortlist, derived: false },
    { label: "초안 작성", count: screened, derived: false },
    { label: "브랜드 세이프", count: brandSafe || Math.round(screened * 0.65), derived: !brandSafe },
    { label: "승인", count: Math.round((brandSafe || screened * 0.65) * 0.7), derived: true },
    { label: "응답", count: Math.round((brandSafe || screened * 0.65) * 0.7 * 0.35), derived: true },
  ];
  // Enforce monotonic non-increasing counts (each stage <= previous).
  for (let i = 1; i < stages.length; i += 1) {
    stages[i].count = Math.min(stages[i].count, stages[i - 1].count);
  }
  const top = stages[0].count || 1;
  return stages.map((stage) => ({
    ...stage,
    percent: Math.round((stage.count / top) * 100),
  }));
}

function renderCampaignFunnel() {
  const container = byId("campaignFunnel");
  if (!container) return;
  const stages = buildCampaignFunnel();
  container.innerHTML = stages
    .map(
      (stage) =>
        `<div style="--stage:${stage.percent}%"><strong>${stage.count}${
          stage.derived ? '<i class="derived-tag" title="문서화된 전환율로 파생한 추정치 (실측 아님)">추정</i>' : ""
        }</strong>` + `<span>${stage.label}</span><em>${stage.percent}%</em></div>`
    )
    .join("");
  const note = byId("campaignFunnelNote");
  if (note) {
    const derivedLabels = stages.filter((stage) => stage.derived).map((stage) => stage.label);
    note.textContent = derivedLabels.length
      ? `추정 = 문서화된 전환율(65%/70%/35%)로 파생: ${derivedLabels.join(", ")} · 숏리스트·초안은 실카운트`
      : "전 단계 실측 카운트";
  }
}

function renderCommerceCommand() {
  const metrics = buildCommandMetrics();
  const stages = [
    ["발굴", state.creators.length + state.intakeCreators.length, "후보 풀"],
    ["최근 20", `${metrics.loadedRecentPosts}/${metrics.requiredRecentPosts}`, `커버리지 ${metrics.coveragePercent}%`],
    ["스크리닝", metrics.screenedCount, "AI 1차"],
    ["아웃리치 준비", metrics.outreachReadyCount, "통과 + 낮은 리스크"],
    ["수동 검수", metrics.humanReviewLoad, "리스크·데이터 게이트"],
    ["게시 추적", 0, "추적 대기"],
  ];
  byId("commerceCommand").innerHTML = `
    <div class="command-summary">
      <div>
        <span>예상 GMV</span>
        <strong>${escapeHtml(formatCurrencyCompact(metrics.pipelineGmvUsd))}</strong>
        <small>파일럿 목표 대비 ${escapeHtml(metrics.targetProgress)}%</small>
      </div>
      <div>
        <span>유효 도달</span>
        <strong>${escapeHtml(formatCompactNumber(metrics.qualifiedReach))}</strong>
        <small>월 평균 조회 기반</small>
      </div>
      <div>
        <span>데이터 신뢰도</span>
        <strong>${escapeHtml(String(metrics.coveragePercent))}%</strong>
        <small>최근 20개 완성도</small>
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
      label: "데이터 보완",
      title: "최근 20개 게시물 공백",
      detail: gapCreators
        .map((creator) => `@${creator.username} ${loadedRecentPostsCount(creator)}/20`)
        .join(" · "),
      next: "후보 인테이크",
    });
  }

  if (readyCreators.length) {
    actions.push({
      tier: "green",
      label: "아웃리치",
      title: "DM 검수 준비 후보",
      detail: readyCreators.map((creator) => `@${creator.username}`).join(" · "),
      next: "브랜드 세이프티",
    });
  }

  const auditRisk = (state.coverageAudit || []).filter((item) => (item.missing_intent_types || []).length > 0);
  if (auditRisk.length) {
    actions.push({
      tier: "blue",
      label: "발굴 리콜",
      title: "2차 확장",
      detail: `시장/제품 셀 ${auditRisk.length}곳에 intent 커버리지 누락`,
      next: "크리에이터 발굴",
    });
  }

  actions.push({
    tier: state.apiOnline ? "green" : "neutral",
    label: "시스템",
    title: `${state.systemReadiness.api} · ${state.systemReadiness.readiness}`,
    detail: state.systemReadiness.note,
    next: `유효 조회 기반 ${formatCompactNumber(metrics.qualifiedReach)}`,
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

function renderOperationsPipelineSummary() {
  const target = byId("operationsPipelineSummary");
  if (!target) return;
  const pipeline = state.operationsPipeline;
  const steps = [
    ["수집", pipeline?.acquisition?.status || "준비"],
    ["임포트 로그", pipeline?.importQuality?.status || "준비"],
    ["Enrichment", pipeline?.enrichment?.status || "대기"],
    ["최근 20 반영", pipeline?.recentApply?.status || "대기"],
    ["캠페인 매칭", pipeline?.match?.summary?.matched_count ?? "대기"],
    ["아웃리치 플랜", pipeline?.outreachPlan?.items?.length ?? "대기"],
    ["CRM 보드", pipeline?.crm?.board?.total ?? "대기"],
    ["성과", pipeline?.performance?.rollup?.summary?.revenue_usd ?? "대기"],
  ];
  target.innerHTML = steps
    .map(
      ([label, value], index) => `
      <article class="pipeline-step" style="--stage-color:${escapeHtml(stageColor(index))}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(formatPipelineValue(label, value))}</strong>
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

// --- Per-screen KPI strips (Phase 3 remainder) ---------------------------------
// Same contract as buildCampaignFunnel: every number is anchored to live state.
// candidates = creator pool + screening state; tracking/settlement = the session
// write logs (state.sessionSnapshots 등), so counts only move when a write actually
// completed (cancelled or API-rejected writes never land in the logs).

function buildCandidateKpis() {
  const metrics = buildCommandMetrics();
  const creators = state.creators;
  const scored = creators.filter((creator) => Number.isFinite(Number(creator.final_score)));
  const averageScore = scored.length
    ? Math.round(scored.reduce((sum, creator) => sum + Number(creator.final_score), 0) / scored.length)
    : 0;
  const markets = new Set(creators.map((creator) => creator.country).filter(Boolean));
  const topCreator = [...scored].sort((a, b) => Number(b.final_score) - Number(a.final_score))[0];
  return [
    {
      label: "활성 후보 풀",
      value: String(creators.length + state.intakeCreators.length),
      note: `시장 ${markets.size}곳 · 인테이크 대기 ${state.intakeCreators.length}`,
    },
    {
      label: "평균 적합 점수",
      value: String(averageScore),
      note: topCreator ? `최고 @${topCreator.username} ${topCreator.final_score}점` : "점수 데이터 없음",
    },
    {
      label: "스크리닝 완료",
      value: `${metrics.screenedCount}/${creators.length}`,
      note: `최근 20개 커버리지 ${metrics.coveragePercent}%`,
    },
    {
      label: "아웃리치 준비",
      value: String(metrics.outreachReadyCount),
      note: `낮은 리스크 ${metrics.lowRiskCount}명 · 데이터 공백 ${metrics.postGapCount}명`,
    },
  ];
}

function buildTrackingKpis() {
  const snapshots = state.sessionSnapshots;
  const liveCount = snapshots.filter((entry) => entry.recorded === "live").length;
  const totalViews = snapshots.reduce((sum, entry) => sum + Number(entry.view_count || 0), 0);
  const revenueUsd = snapshots.reduce((sum, entry) => sum + Number(entry.revenue_usd || 0), 0);
  const rollupRevenue = state.operationsPipeline?.performance?.rollup?.summary?.revenue_usd;
  return [
    {
      label: "세션 스냅샷",
      value: String(snapshots.length),
      note: snapshots.length
        ? `라이브 기록 ${liveCount} · 미리보기 ${snapshots.length - liveCount}`
        : "스냅샷 저장 시 집계 시작",
    },
    {
      label: "추적 조회수",
      value: formatCompactNumber(totalViews),
      note: "세션 저장 스냅샷 합계",
    },
    {
      label: "매출 (USD 환산)",
      value: formatCurrencyCompact(revenueUsd),
      note: "기록시점 FX 환산 · USD 25K 파일럿 목표",
    },
    {
      label: "운영 rollup 매출",
      value: rollupRevenue == null ? "대기" : formatCurrencyCompact(rollupRevenue),
      note: rollupRevenue == null ? "운영 파이프라인 실행 시 집계" : "성과 rollup 기준",
    },
  ];
}

function buildSettlementKpis() {
  const pendingRows = PAYOUT_ROWS.filter((row) => row.status === "pending");
  const blockedRows = PAYOUT_ROWS.filter((row) => row.status === "blocked");
  const pendingUsd = pendingRows.reduce((sum, row) => sum + row.amount_usd, 0);
  const contractFeeUsd = state.sessionContracts.reduce((sum, entry) => sum + Number(entry.fee_usd || 0), 0);
  const codes = state.sessionDiscountCodes;
  const liveCodes = codes.filter((entry) => entry.mode === "live").length;
  return [
    {
      label: "지급 대기",
      value: formatCurrencyCompact(pendingUsd),
      note: `대기 ${pendingRows.length}건 · 증빙 확인 후 지급`,
    },
    {
      label: "증빙 차단",
      value: String(blockedRows.length),
      note: blockedRows.length ? blockedRows.map((row) => `${row.creator} ${row.blocker}`).join(" · ") : "차단 없음",
    },
    {
      label: "세션 계약 저장",
      value: String(state.sessionContracts.length),
      note: state.sessionContracts.length
        ? `비용 합계 ${formatCurrencyCompact(contractFeeUsd)}`
        : "계약 저장 시 집계 시작",
    },
    {
      label: "할인코드 발급",
      value: String(codes.length),
      note: codes.length ? `라이브 ${liveCodes} · 드라이런/미리보기 ${codes.length - liveCodes}` : "발급 시 집계 시작",
    },
  ];
}

function renderScreenKpis() {
  const mounts = [
    ["candidatesKpis", buildCandidateKpis],
    ["trackingKpis", buildTrackingKpis],
    ["settlementKpis", buildSettlementKpis],
  ];
  mounts.forEach(([id, build]) => {
    const mount = byId(id);
    if (!mount) return;
    mount.innerHTML = build()
      .map(
        (kpi) => `
      <article class="metric-card">
        <span class="metric-label">${escapeHtml(kpi.label)}</span>
        <strong>${escapeHtml(kpi.value)}</strong>
        <small>${escapeHtml(kpi.note)}</small>
      </article>
    `
      )
      .join("");
  });
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
  const csvLoaded = creators === state.intakeCreators && state.intakeCreators.length > 0;
  const headerReport = csvLoaded
    ? buildHeaderReport(state.intakeCreatorHeaders, REQUIRED_CREATOR_COLUMNS, RECOMMENDED_CREATOR_COLUMNS)
    : buildHeaderReport([], [], []);
  const sourceTypeCounts = {};
  const riskCounts = {};

  headerReport.missing_required.forEach((column) => {
    blockers.push(`Creator CSV: required column ${column} missing`);
  });
  headerReport.missing_recommended.forEach((column) => {
    warnings.push(`Creator CSV: recommended column ${column} missing`);
  });

  creators.forEach((creator, index) => {
    const rowLabel = creator.username ? `@${creator.username}` : `row ${index + 1}`;
    const creatorKey = creator.creator_id || creator.username || `row-${index}`;
    const sourceType = normalizeSourceType(creator.source_type);
    const sourceRisk = normalizeRisk(creator.source_risk_level);
    incrementCount(sourceTypeCounts, sourceType || "missing");
    incrementCount(riskCounts, sourceRisk || "missing");
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
    if (!ALLOWED_IMPORT_SOURCE_TYPES.includes(sourceType)) {
      blockers.push(`${rowLabel}: source_type must be manual, official_api, approved_provider, or creator_provided`);
      invalidCreatorIds.add(creatorKey);
    }
    if (!["low", "low_medium", "medium"].includes(sourceRisk)) {
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

  const approvedSourceTypes = Object.keys(sourceTypeCounts).filter((type) => ALLOWED_IMPORT_SOURCE_TYPES.includes(type));
  if (approvedSourceTypes.length > 1) {
    blockers.push("Creator CSV: split mixed source_type values into separate uploads before DB import");
  }

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
    source_type_counts: sourceTypeCounts,
    risk_counts: riskCounts,
    header_report: headerReport,
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
  const sourceTypeCounts = {};
  const riskCounts = {};
  const headerReports = [];
  let creatorsReady = 0;

  creators.forEach((creator) => {
    const posts = state.recentPostsByCreator[creator.creator_id] || [];
    const headerReport = buildHeaderReport(
      state.recentPostHeadersByCreator[creator.creator_id] || [],
      state.recentPostHeadersByCreator[creator.creator_id]?.length ? REQUIRED_POST_COLUMNS : [],
      state.recentPostHeadersByCreator[creator.creator_id]?.length ? RECOMMENDED_POST_COLUMNS : []
    );
    if (headerReport.detected_count) {
      headerReports.push({
        creator_id: creator.creator_id,
        username: creator.username,
        ...headerReport,
      });
      headerReport.missing_required.forEach((column) => {
        blockers.push(`@${creator.username}: post CSV required column ${column} missing`);
      });
      headerReport.missing_recommended.forEach((column) => {
        warnings.push(`@${creator.username}: post CSV recommended column ${column} missing`);
      });
    }
    loaded += Math.min(20, posts.length);
    if (posts.length === 0) {
      blockers.push(`@${creator.username}: recent 20 posts missing`);
      return;
    }
    if (posts.length >= 20) creatorsReady += 1;
    if (posts.length < 20) {
      blockers.push(`@${creator.username}: ${posts.length}/20 recent posts loaded`);
    }
    const duplicateUrls = findDuplicates(posts.map((post) => post.url).filter(Boolean));
    duplicateUrls.forEach((url) => blockers.push(`@${creator.username}: duplicate post URL ${url}`));
    const missingUrls = posts.filter((post) => !post.url).length;
    const missingCaptions = posts.filter((post) => !post.caption).length;
    const missingMetrics = posts.filter((post) => !post.view_count && !post.like_count && !post.comment_count).length;
    const missingTranscripts = posts.filter((post) => !post.transcript).length;
    posts.forEach((post, index) => {
      const sourceType = normalizeSourceType(post.source_type || creator.source_type);
      const sourceRisk = normalizeRisk(post.source_risk_level || creator.source_risk_level);
      incrementCount(sourceTypeCounts, sourceType || "missing");
      incrementCount(riskCounts, sourceRisk || "missing");
      if (!ALLOWED_IMPORT_SOURCE_TYPES.includes(sourceType)) {
        blockers.push(`@${creator.username}: post ${index + 1} has unapproved source_type`);
      }
      if (!["low", "low_medium", "medium"].includes(sourceRisk)) {
        blockers.push(`@${creator.username}: post ${index + 1} has blocked source_risk_level`);
      }
    });
    const postApprovedSourceTypes = unique(posts.map((post) => normalizeSourceType(post.source_type || creator.source_type)))
      .filter((type) => ALLOWED_IMPORT_SOURCE_TYPES.includes(type));
    if (postApprovedSourceTypes.length > 1) {
      blockers.push(`@${creator.username}: split mixed post source_type values into separate uploads before DB import`);
    }
    if (missingUrls) blockers.push(`@${creator.username}: ${missingUrls} posts missing URL`);
    if (missingCaptions) warnings.push(`@${creator.username}: ${missingCaptions} posts missing captions`);
    if (missingMetrics) warnings.push(`@${creator.username}: ${missingMetrics} posts missing public metrics`);
    if (missingTranscripts) warnings.push(`@${creator.username}: ${missingTranscripts} posts missing transcripts`);
  });

  return {
    loaded,
    required,
    coverage_percent: required ? Math.round((loaded / required) * 100) : 0,
    creators_ready: creatorsReady,
    source_type_counts: sourceTypeCounts,
    risk_counts: riskCounts,
    header_reports: headerReports,
    blockers: unique(blockers),
    warnings: unique(warnings),
  };
}

function buildQualitySummary(status, blockers, warnings) {
  if (status === "blocked") return `등록·스크리닝 전 블로커 ${blockers}건을 해결해야 합니다.`;
  if (status === "needs_review") return `아웃리치 전 경고 ${warnings}건에 대한 운영자 검수가 필요합니다.`;
  return "등록·스크리닝·운영자 검수 준비 완료.";
}

function buildHeaderReport(headers, requiredColumns, recommendedColumns) {
  const normalized = unique((headers || []).map(normalizeHeader).filter(Boolean));
  return {
    detected: normalized,
    detected_count: normalized.length,
    missing_required: missingColumns(normalized, requiredColumns),
    missing_recommended: missingColumns(normalized, recommendedColumns),
  };
}

function missingColumns(headers, columns) {
  const present = new Set((headers || []).map(normalizeHeader));
  return (columns || []).filter((column) => !present.has(normalizeHeader(column)));
}

function incrementCount(target, key) {
  const normalized = String(key || "missing").trim() || "missing";
  target[normalized] = (target[normalized] || 0) + 1;
}

function countBy(items, key) {
  return (items || []).reduce((counts, item) => {
    incrementCount(counts, item?.[key]);
    return counts;
  }, {});
}

function mergeCountObjects(...objects) {
  return objects.reduce((merged, object) => {
    Object.entries(object || {}).forEach(([key, value]) => {
      merged[key] = (merged[key] || 0) + Number(value || 0);
    });
    return merged;
  }, {});
}

function objectCountSummary(object) {
  return Object.entries(object || {})
    .filter(([, value]) => Number(value || 0) > 0)
    .map(([key, value]) => `${key}:${value}`)
    .join(" · ");
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
    ready: "준비완료",
    needs_review: "검수 필요",
    blocked: "차단",
  };
  return labels[status] || status;
}

function canPersistOperationCreators(creators) {
  return creators.every((creator) => looksLikeUuid(creator.creator_id));
}

function looksLikeUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    String(value || "")
  );
}

function formatPipelineValue(label, value) {
  if (label === "성과" && typeof value === "number") {
    return formatCurrencyCompact(value);
  }
  return String(value);
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
          <span>적합 ${escapeHtml(String(creator.final_score || 0))}</span>
          <span>평균조회 ${escapeHtml(formatCompactNumber(creator.avg_views))}</span>
          <span>ER ${escapeHtml(formatPercent(creator.engagement_rate))}</span>
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
        <td><button class="button" data-select-creator="${escapeHtml(creator.creator_id)}">검수</button></td>
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
        <td><button class="button" data-select-creator="${escapeHtml(creator.creator_id)}">프로필 열기</button></td>
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
      <div><span>팔로워</span><strong>${escapeHtml(formatCompactNumber(creator.follower_count))}</strong></div>
      <div><span>평균 조회</span><strong>${escapeHtml(formatCompactNumber(creator.avg_views))}</strong></div>
      <div><span>인게이지먼트</span><strong>${escapeHtml(formatPercent(creator.engagement_rate))}</strong></div>
      <div><span>적합 점수</span><strong>${escapeHtml(String(creator.final_score || 0))}</strong></div>
    </div>
    <div class="signal-list">${signalTags(creator.signals)}</div>
    <div class="policy-line"><span>리스크 패널티</span><strong>${escapeHtml(String(creator.risk_penalty || 0))}</strong></div>
    <div class="policy-line"><span>추천 포맷</span><strong>${escapeHtml(formatSegment(creator.segment || "review_creator"))}</strong></div>
    <p>${escapeHtml(creator.recommended_campaign_angle || "협업 전 최종 검수 필요")}</p>
    ${screen ? renderScreenCompact(screen) : renderScreenPlaceholder(creator.creator_id)}
    <div class="detail-actions">
      <button class="button primary" data-add-to-campaign="${escapeHtml(creator.creator_id)}">후보 숏리스트</button>
      <button class="button" data-run-recent-screen="${escapeHtml(creator.creator_id)}">최근 20개 스크리닝 실행</button>
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
    <div class="policy-line"><span>허용 소스</span><strong>${escapeHtml(formatSourceTypes(source.allowed_source_types).join(", "))}</strong></div>
    <div class="policy-line"><span>차단 소스</span><strong>${escapeHtml(formatSourceTypes(source.blocked_source_types).join(", "))}</strong></div>
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
  state.aiProvider = source;
  byId("aiProvider").innerHTML = `
    <div class="policy-line"><span>기본 Provider</span><strong>${escapeHtml(formatProvider(source.provider || "google"))}</strong></div>
    <div class="policy-line"><span>어댑터</span><strong>${escapeHtml(formatAdapter(source.default_adapter || "GeminiTextAdapter"))}</strong></div>
    <div class="policy-line"><span>라이브 호출</span><strong>${escapeHtml(formatBoolean(Boolean(source.live_ready)))}</strong></div>
    <div class="policy-line"><span>드라이런</span><strong>${escapeHtml(formatBoolean(Boolean(source.dry_run)))}</strong></div>
  `;
  updateRecentScreenModeAvailability();
}

function updateRecentScreenModeAvailability() {
  const select = byId("recentScreenMode");
  const hint = byId("recentScreenModeHint");
  if (!select) return;
  const liveOption = Array.from(select.options).find((option) => option.value === "live");
  const liveReady = Boolean(state.aiProvider?.live_ready);
  if (liveOption) liveOption.disabled = !liveReady;
  if (!liveReady && select.value === "live") {
    select.value = "dry_run";
    localStorage.setItem("briwell.recentScreenMode", "dry_run");
  }
  if (hint) {
    hint.textContent = liveReady
      ? "라이브 Gemini 준비됨. 호출은 비용·횟수 제한 및 로깅됩니다."
      : "라이브 Gemini 사용 불가. API, AI_DRY_RUN=false, ALLOW_LIVE_PROVIDER_CALLS=true, GEMINI_API_KEY를 확인하세요.";
  }
}

// Single source for payout preview rows so the payout table and the settlement
// KPI strip can never disagree. amount_usd is numeric for aggregation.
const PAYOUT_ROWS = [
  { creator: "@luzskincare", amount_usd: 150, status: "pending", blocker: "게시물 URL" },
  { creator: "@pielconandrea", amount_usd: 220, status: "blocked", blocker: "인보이스 URL" },
  { creator: "@rutina.ec", amount_usd: 120, status: "pending", blocker: "세금 증빙" },
];

function renderPayoutTable() {
  byId("payoutTable").innerHTML = PAYOUT_ROWS.map(
    (row) => `
      <tr>
        <td>${escapeHtml(row.creator)}</td>
        <td>${escapeHtml(formatCurrencyCompact(row.amount_usd))}</td>
        <td>${row.status === "blocked" ? '<span class="badge red">차단</span>' : '<span class="badge amber">대기</span>'}</td>
        <td>${escapeHtml(row.blocker)}</td>
      </tr>
    `
  ).join("");
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
        <span>전체 상태</span>
        <strong>${escapeHtml(formatQualityStatus(quality.overall_status))}</strong>
        <small>${escapeHtml(quality.summary)}</small>
      </article>
      <article>
        <span>크리에이터 데이터</span>
        <strong>${escapeHtml(String(quality.creator.total))}</strong>
        <small>유효 ${escapeHtml(quality.creator.valid)} · 블로커 ${escapeHtml(quality.creator.blockers.length)}</small>
      </article>
      <article>
        <span>최근 게시물</span>
        <strong>${escapeHtml(String(quality.posts.loaded))}/${escapeHtml(String(quality.posts.required))}</strong>
        <small>커버리지 ${escapeHtml(quality.posts.coverage_percent)}% · 블로커 ${escapeHtml(quality.posts.blockers.length)}</small>
      </article>
      <article>
        <span>시장 커버리지</span>
        <strong>${escapeHtml(quality.creator.market_coverage.join(" · ") || "없음")}</strong>
        <small>MX·PE·EC 런칭 클러스터</small>
      </article>
    </div>
    ${renderValidationReport(quality)}
    <div class="quality-columns">
      ${renderQualityColumn("크리에이터 블로커", quality.creator.blockers, "red")}
      ${renderQualityColumn("크리에이터 경고", quality.creator.warnings, "amber")}
      ${renderQualityColumn("게시물 블로커", quality.posts.blockers, "red")}
      ${renderQualityColumn("게시물 경고", quality.posts.warnings, "amber")}
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

function renderValidationReport(quality) {
  const creatorHeader = quality.creator.header_report || buildHeaderReport([], [], []);
  const postReports = quality.posts.header_reports || [];
  const postMissingRequired = unique(postReports.flatMap((report) => report.missing_required || []));
  const postMissingRecommended = unique(postReports.flatMap((report) => report.missing_recommended || []));
  const sourceTypes = mergeCountObjects(quality.creator.source_type_counts, quality.posts.source_type_counts);
  const riskMix = mergeCountObjects(quality.creator.risk_counts, quality.posts.risk_counts);
  const sourceTypeKeys = Object.keys(sourceTypes);
  const creatorContractReady = !creatorHeader.missing_required.length;
  const postsContractReady = !postMissingRequired.length && quality.posts.coverage_percent >= 100;
  const sourceReady = sourceTypeKeys.every((type) => ALLOWED_IMPORT_SOURCE_TYPES.includes(type)) && sourceTypeKeys.length <= 1;
  const dbReady = quality.overall_status !== "blocked";
  const cards = [
    {
      title: "크리에이터 CSV 계약",
      value: creatorContractReady ? "준비" : "수정 필요",
      tone: creatorContractReady ? "green" : "red",
      meta: `${quality.creator.total}행 · ${creatorHeader.detected_count || "시드"}열`,
      items: creatorHeader.missing_required.length
        ? creatorHeader.missing_required.map((column) => `필수: ${column}`)
        : (creatorHeader.missing_recommended.length
          ? creatorHeader.missing_recommended.slice(0, 4).map((column) => `권장: ${column}`)
          : ["필수 컬럼 확인됨"]),
    },
    {
      title: "최근 20개 계약",
      value: postsContractReady ? "스크리닝 준비" : `${quality.posts.creators_ready}/${quality.creator.total} 준비`,
      tone: postsContractReady ? "green" : "amber",
      meta: `게시물 ${quality.posts.loaded}/${quality.posts.required} · 커버리지 ${quality.posts.coverage_percent}%`,
      items: postMissingRequired.length
        ? postMissingRequired.map((column) => `필수: ${column}`)
        : (postMissingRecommended.length
          ? postMissingRecommended.slice(0, 4).map((column) => `권장: ${column}`)
          : ["최근 게시물 계약 충족"]),
    },
    {
      title: "소스 거버넌스",
      value: sourceReady ? "승인" : "차단",
      tone: sourceReady ? "blue" : "red",
      meta: objectCountSummary(sourceTypes) || "수동 미리보기",
      items: [`리스크 구성: ${objectCountSummary(riskMix) || "low"}`],
    },
    {
      title: "DB E2E 게이트",
      value: dbReady ? "저장 가능" : "보류",
      tone: dbReady ? "green" : "red",
      meta: dbReady ? "임포트 로그·DB 워크플로우 준비" : "저장 전 블로커 해결 필요",
      items: [
        quality.overall_status === "ready"
          ? "크리에이터·게시물·소스 검사 통과"
          : `블로커 ${quality.creator.blockers.length + quality.posts.blockers.length} · 경고 ${quality.creator.warnings.length + quality.posts.warnings.length}`,
      ],
    },
  ];
  return `
    <div class="validation-report">
      ${cards.map(renderValidationReportCard).join("")}
    </div>
  `;
}

function renderValidationReportCard(card) {
  return `
    <article class="validation-card ${escapeHtml(card.tone)}">
      <span>${escapeHtml(card.title)}</span>
      <strong>${escapeHtml(card.value)}</strong>
      <small>${escapeHtml(card.meta)}</small>
      <ul>
        ${(card.items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </article>
  `;
}

function renderQualityColumn(title, items, tone) {
  const rendered = items.length
    ? items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : `<li class="quality-empty">없음</li>`;
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
        <strong>${creator ? `@${escapeHtml(creator.username)}` : "대상 크리에이터"}</strong>
        <span>최근 게시물 ${escapeHtml(posts.length)} / 20 적재</span>
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
          <div><span>선택</span><strong>${escapeHtml(String(item.selected_count || 0))}</strong></div>
          <div><span>가능</span><strong>${escapeHtml(String(item.available_count || 0))}</strong></div>
          <div><span>누락</span><strong>${escapeHtml(String((item.missing_intent_types || []).length))}</strong></div>
        </div>
        <div class="tag-row">${(item.missing_intent_types || []).map((value) => `<span class="badge amber">${escapeHtml(formatIntent(value))}</span>`).join("") || '<span class="badge green">균형</span>'}</div>
        <p>${escapeHtml((item.false_negative_risks || [])[0] || "초기 조건으로 인한 누락 리스크 낮음")}</p>
        <small>${escapeHtml((item.recommended_actions || [])[0] || "최근 20개 게시물 스크리닝으로 최종 제외 전 확인")}</small>
      </article>
    `
      )
      .join("") || `<div class="screening-empty"><strong>커버리지 감사 없음</strong><span>발굴 브리프 생성 후 표시</span></div>`;

  byId("recallSafeguards").innerHTML = (state.recallSafeguards || [])
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
}

async function runDiscoveryPlan() {
  const countries = Array.from(byId("discoveryCountries").selectedOptions).map((item) => item.value);
  const product = byId("discoveryProduct").value;
  const platform = byId("discoveryPlatform").value;
  const limit = Number(byId("discoveryLimit").value || 4);
  const previewRows = buildPreviewDiscoveryRows(countries, product, platform, limit);

  try {
    const payload = await window.BriwellApi.createDiscoveryPlan({
      countries,
      product_categories: [product],
      platforms: [platform],
      max_keywords_per_country_category: limit,
      include_coverage_audit: true,
    });
    renderDiscoveryRows(payload.items || previewRows);
    state.coverageAudit = payload.coverage_audit || buildPreviewCoverageAudit(countries, product, limit);
    state.recallSafeguards = payload.recall_safeguards || buildPreviewRecallSafeguards();
    renderCoverageAudit();
  } catch (error) {
    if (error.cancelled) {
      showToast("취소됨 · 아무것도 기록되지 않음");
      return;
    }
    renderDiscoveryRows(previewRows);
    state.coverageAudit = buildPreviewCoverageAudit(countries, product, limit);
    state.recallSafeguards = buildPreviewRecallSafeguards();
    renderCoverageAudit();
  }
}

async function loadKeywordPlaybook() {
  const countries = Array.from(byId("discoveryCountries").selectedOptions).map((item) => item.value);
  const product = byId("discoveryProduct").value;
  const limit = Number(byId("discoveryLimit").value || 8);
  try {
    const payload = await window.BriwellApi.getTiktokKeywordPlaybook({
      countries: countries.join(","),
      product_categories: product,
      max_keywords_per_country_category: limit,
    });
    state.keywordPlaybook = payload;
    renderKeywordPlaybookSummary();
    showResult("tiktokProviderResult", payload);
    showToast(`K-Beauty 키워드 ${payload.keyword_count || 0}개 불러옴`);
  } catch (error) {
    state.keywordPlaybook = buildLocalKeywordPlaybook(countries, product, limit);
    renderKeywordPlaybookSummary();
    showResult("tiktokProviderResult", error.payload || {
      status: "local_keyword_preview",
      message: error.message,
      ...state.keywordPlaybook,
    });
  }
}

async function runTiktokProviderDiscovery() {
  const countries = Array.from(byId("discoveryCountries").selectedOptions).map((item) => item.value);
  const product = byId("discoveryProduct").value;
  const keywordLimit = Number(byId("discoveryLimit").value || 8);
  const mode = byId("tiktokProviderMode").value;
  const payload = {
    provider: byId("tiktokProviderSelect").value,
    countries,
    product_categories: [product],
    max_keywords_per_country_category: keywordLimit,
    max_results_per_query: Number(byId("tiktokProviderResults").value || 3),
    recent_posts_per_creator: Number(byId("tiktokProviderPosts").value || 20),
    include_recent_posts: true,
    dry_run: mode !== "live",
    allow_live_provider_calls: mode === "live",
    persist_imports: false,
  };
  try {
    const response = await window.BriwellApi.runTiktokProviderDiscovery(payload);
    state.tiktokProviderRun = response;
    applyProviderRunToPreview(response);
    renderKeywordPlaybookSummary();
    showResult("tiktokProviderResult", response);
    showToast(`Provider 크리에이터 ${response.creator_count || 0}명 준비됨`);
  } catch (error) {
    showResult("tiktokProviderResult", error.payload || { status: "provider_run_failed", message: error.message });
  }
  renderAll();
}

function renderKeywordPlaybookSummary() {
  const target = byId("keywordPlaybookSummary");
  if (!target) return;
  const playbook = state.keywordPlaybook;
  const providerRun = state.tiktokProviderRun;
  const items = playbook?.items || [];
  const intentCounts = objectCountSummary(countBy(items, "intent_type")) || "Not loaded";
  const cards = [
    ["Keywords", playbook?.keyword_count ?? items.length ?? 0],
    ["Intent Mix", intentCounts],
    ["Provider", providerRun?.provider || byId("tiktokProviderSelect")?.value || "apify"],
    ["Creators", providerRun?.creator_count ?? "Pending"],
    ["Recent Posts", providerRun?.video_count ?? "Pending"],
  ];
  target.innerHTML = cards
    .map(
      ([label, value]) => `
      <article class="provider-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(String(value))}</strong>
      </article>
    `
    )
    .join("");
}

function applyProviderRunToPreview(response) {
  if (!response || !Array.isArray(response.creators)) return;
  const creators = response.creators.map(normalizeProviderCreator);
  state.creators = mergeCreators(state.creators, creators);
  (response.creators || []).forEach((creator) => {
    const normalized = normalizeProviderCreator(creator);
    const videos = response.videos_by_creator?.[creator.provider_creator_id] || [];
    if (videos.length) {
      state.recentPostsByCreator[normalized.creator_id] = videos.map((video) => normalizeProviderVideo(video, normalized.creator_id));
    }
  });
}

async function loadCreatorCsv() {
  try {
    const text = await readFileInput("creatorCsvInput");
    const parsed = parseCsvWithMeta(text);
    state.intakeCreatorHeaders = parsed.headers;
    state.intakeCreators = parsed.rows.map(normalizeCsvCreator);
    renderCreatorImportPreview();
    renderImportQualityGate();
    showResult("creatorImportResult", {
      status: "preview_ready",
      preview_count: state.intakeCreators.length,
      source_risk_level: highestRiskLevel(state.intakeCreators),
      missing_required_columns: state.importQuality?.creator?.header_report?.missing_required || [],
      missing_recommended_columns: state.importQuality?.creator?.header_report?.missing_recommended || [],
    });
    showToast(`후보 크리에이터 ${state.intakeCreators.length}명 불러옴`);
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
    source_type: sourceTypeForImport(state.intakeCreators),
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
    if (!error.cancelled) {
      state.creators = mergeCreators(state.creators, state.intakeCreators);
    }
    showResult("creatorImportResult", error.payload || { status: "local_preview_imported", accepted: state.intakeCreators.length });
    if (error.cancelled) {
      renderAll();
      showToast("취소됨 · 아무것도 기록되지 않음");
      return;
    }
  }
  renderAll();
  showToast("크리에이터 등록 완료");
}

async function loadPostCsv() {
  try {
    const creatorId = byId("postCreatorSelect").value;
    const text = await readFileInput("postCsvInput");
    const parsed = parseCsvWithMeta(text);
    const posts = parsed.rows.map((row, index) => normalizeCsvPost(row, creatorId, index));
    state.recentPostHeadersByCreator[creatorId] = parsed.headers;
    state.recentPostsByCreator[creatorId] = posts.slice(0, 20);
    renderPostImportTable();
    renderImportQualityGate();
    renderRecentScreenResult(creatorId);
    showResult("postImportResult", {
      status: "preview_ready",
      creator_id: creatorId,
      recent_posts_loaded: state.recentPostsByCreator[creatorId].length,
      missing_required_columns:
        state.importQuality?.posts?.header_reports?.find((item) => item.creator_id === creatorId)?.missing_required || [],
    });
  } catch (error) {
    showResult("postImportResult", { status: "preview_failed", message: error.message });
  }
}

function loadManualPosts() {
  try {
    const creatorId = byId("postCreatorSelect").value;
    const text = byId("manualPostsInput").value.trim();
    const parsed = parseManualPostsWithMeta(text);
    const posts = parsed.rows.map((row, index) => normalizeCsvPost(row, creatorId, index));
    state.recentPostHeadersByCreator[creatorId] = parsed.headers;
    state.recentPostsByCreator[creatorId] = posts.slice(0, 20);
    renderPostImportTable();
    renderImportQualityGate();
    renderRecentScreenResult(creatorId);
    showResult("postImportResult", {
      status: "manual_preview_ready",
      creator_id: creatorId,
      recent_posts_loaded: state.recentPostsByCreator[creatorId].length,
      missing_required_columns:
        state.importQuality?.posts?.header_reports?.find((item) => item.creator_id === creatorId)?.missing_required || [],
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
    source_type: sourceTypeForImport(posts),
    source_risk_level: highestRiskLevel(posts),
    items: posts.map(toVideoImportItem),
  };
  try {
    showResult("postImportResult", await window.BriwellApi.importVideos(payload));
  } catch (error) {
    showResult("postImportResult", error.payload || { status: "local_preview_imported", creator_id: creatorId, accepted: posts.length });
    if (error.cancelled) {
      showToast("취소됨 · 아무것도 기록되지 않음");
      return;
    }
  }
  showToast(`최근 게시물 ${posts.length}개 연결됨`);
}

// --- creator_provided submission channel (briefing 0.0.8 → slimmed-C step (a)) ---
// Creators fill the two CSV templates; the operator adds consent_ref/provided_at,
// uploads here, and the rows are normalized through the creator_provided provider
// (pure compute) before flowing into the standard intake/import machinery.

function copyCreatorRequestText() {
  const textarea = byId("creatorRequestText");
  if (!textarea) return;
  const copyText = textarea.value;
  const done = () => showToast("스페인어 요청문 복사됨 · 수동 발송만 허용");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(copyText).then(done, () => fallbackCopy(textarea, done));
  } else {
    fallbackCopy(textarea, done);
  }
}

function fallbackCopy(textarea, done) {
  textarea.focus();
  textarea.select();
  try {
    document.execCommand("copy");
    done();
  } catch (_error) {
    showToast("복사 실패 · 텍스트를 직접 선택해 주세요");
  }
}

function numOrNull(value) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const numeric = Number(text);
  return Number.isNaN(numeric) ? null : numeric;
}

async function parseCreatorProvidedFiles() {
  const profileRows = parseCsv(await readFileInput("cpProfileCsvInput"));
  let postRows = [];
  if (byId("cpPostsCsvInput")?.files?.length) {
    postRows = parseCsv(await readFileInput("cpPostsCsvInput"));
  }

  const issues = [];
  const warnings = [];

  // The provider truncates at max_results (cap 50); block instead of silently
  // dropping submissions past the cap.
  if (profileRows.length > 50) {
    issues.push(`프로필 행 ${profileRows.length}개 — 한 번에 최대 50명까지만 처리됩니다. 파일을 나눠 주세요.`);
  }

  const creators = profileRows.map((row, index) => {
    const label = row.username ? `@${String(row.username).replace(/^@/, "")}` : `프로필 행 ${index + 2}`;
    if (!String(row.username || "").trim()) issues.push(`${label}: username 누락`);
    if (!String(row.country || "").trim()) issues.push(`${label}: country 누락`);
    if (!String(row.consent_ref || "").trim()) issues.push(`${label}: consent_ref(동의 참조) 누락`);
    if (!String(row.provided_at || "").trim()) issues.push(`${label}: provided_at(수신 시각) 누락`);
    return {
      provider_creator_id: String(row.provider_creator_id || "").trim() || undefined,
      country: normalizeCountry(row.country),
      username: String(row.username || "").replace(/^@/, "").trim(),
      display_name: String(row.display_name || "").trim() || undefined,
      profile_url: String(row.profile_url || "").trim() || undefined,
      profile_image_url: String(row.profile_image_url || "").trim() || undefined,
      bio: String(row.bio || "").trim() || undefined,
      follower_count: numOrNull(row.follower_count),
      avg_views: numOrNull(row.avg_views),
      engagement_rate: numOrNull(row.engagement_rate),
      product_category: String(row.product_category || "").trim() || undefined,
      signals: splitList(row.signals),
      consent_ref: String(row.consent_ref || "").trim(),
      provided_at: String(row.provided_at || "").trim(),
    };
  });

  const knownUsernames = new Set(creators.map((creator) => creator.username).filter(Boolean));
  const videosByCreator = {};
  let matchedPostCount = 0;
  postRows.forEach((row, index) => {
    const username = String(row.username || row.provider_creator_id || "").replace(/^@/, "").trim();
    const label = username ? `@${username}` : `게시물 행 ${index + 2}`;
    if (!username) {
      issues.push(`${label}: username 누락`);
      return;
    }
    if (!String(row.url || "").trim()) issues.push(`${label}: url 누락`);
    if (!String(row.consent_ref || "").trim()) issues.push(`${label}: consent_ref(동의 참조) 누락`);
    if (!String(row.provided_at || "").trim()) issues.push(`${label}: provided_at(수신 시각) 누락`);
    if (!knownUsernames.has(username)) {
      // The provider silently drops posts without a matching profile row; warn
      // up front so the operator is never surprised by a lower video_count.
      if (!warnings.includes(`${label}: 프로필 CSV에 없는 계정 — 게시물 제외됨`)) {
        warnings.push(`${label}: 프로필 CSV에 없는 계정 — 게시물 제외됨`);
      }
      return;
    }
    matchedPostCount += 1;
    (videosByCreator[username] = videosByCreator[username] || []).push({
      url: String(row.url || "").trim(),
      platform_video_id: String(row.platform_video_id || "").trim() || undefined,
      caption: String(row.caption || "").trim() || undefined,
      hashtags: splitList(row.hashtags),
      posted_at: String(row.posted_at || "").trim() || null,
      view_count: numOrNull(row.view_count),
      like_count: numOrNull(row.like_count),
      comment_count: numOrNull(row.comment_count),
      share_count: numOrNull(row.share_count),
      save_count: numOrNull(row.save_count),
      duration_seconds: numOrNull(row.duration_seconds),
      thumbnail_url: String(row.thumbnail_url || "").trim() || undefined,
      transcript: String(row.transcript || "").trim() || undefined,
      consent_ref: String(row.consent_ref || "").trim(),
      provided_at: String(row.provided_at || "").trim(),
    });
  });

  return { creators, videosByCreator, issues, warnings, matchedPostCount };
}

async function previewCreatorProvided() {
  try {
    const parsed = await parseCreatorProvidedFiles();
    showResult("creatorProvidedResult", {
      status: parsed.issues.length ? "consent_blocked" : "preview_ready",
      creator_count: parsed.creators.length,
      matched_post_count: parsed.matchedPostCount,
      blockers: parsed.issues,
      warnings: parsed.warnings,
    });
    showToast(
      parsed.issues.length
        ? `동의/필수값 누락 ${parsed.issues.length}건 · 정규화 불가`
        : `크리에이터 ${parsed.creators.length}명 · 게시물 ${parsed.matchedPostCount}개 준비됨`
    );
  } catch (error) {
    showResult("creatorProvidedResult", { status: "preview_failed", message: error.message });
  }
}

async function runCreatorProvidedImport() {
  let parsed;
  try {
    parsed = await parseCreatorProvidedFiles();
  } catch (error) {
    showResult("creatorProvidedResult", { status: "preview_failed", message: error.message });
    return;
  }
  if (parsed.issues.length) {
    showResult("creatorProvidedResult", {
      status: "consent_blocked",
      message: "모든 행에 consent_ref와 provided_at(및 username/country/url)이 필요합니다.",
      blockers: parsed.issues,
    });
    showToast("동의 정보 누락 · 정규화 거부됨");
    return;
  }
  if (!parsed.creators.length) {
    showResult("creatorProvidedResult", { status: "empty", message: "프로필 CSV에 행이 없습니다." });
    return;
  }

  const payload = {
    max_results: Math.min(50, Math.max(1, parsed.creators.length)),
    recent_posts_per_creator: 20,
    payload: { creators: parsed.creators, videos_by_creator: parsed.videosByCreator },
  };

  try {
    const response = await window.BriwellApi.importCreatorProvided(payload);
    state.creatorProvidedRun = response;
    applyCreatorProvidedToIntake(response);
    showResult("creatorProvidedResult", response);
    showToast(`크리에이터 제공 데이터 ${response.creator_count || 0}명 정규화 · 인테이크 반영됨`);
  } catch (error) {
    if (error.cancelled) {
      showResult("creatorProvidedResult", error.payload);
      return;
    }
    if (error.payload) {
      // API rejected the payload (e.g. validation) — nothing was normalized.
      showResult("creatorProvidedResult", error.payload);
      return;
    }
    const local = buildLocalCreatorProvidedRun(parsed);
    state.creatorProvidedRun = local;
    applyCreatorProvidedToIntake(local);
    showResult("creatorProvidedResult", {
      status: "local_preview_normalized",
      creator_count: local.creator_count,
      video_count: local.video_count,
    });
    showToast("미리보기 정규화 · API 오프라인");
  }
  renderAll();
}

// Mirrors the server-side creator_provided normalization closely enough for the
// offline preview: same source labels, same provider_creator_id fallback.
function buildLocalCreatorProvidedRun(parsed) {
  const creators = parsed.creators.map((row) => ({
    ...row,
    provider: "creator_provided",
    provider_creator_id: row.provider_creator_id || row.username,
    source_type: "creator_provided",
    source_risk_level: "low",
  }));
  const videosByCreator = {};
  Object.entries(parsed.videosByCreator).forEach(([username, videos]) => {
    const creator = creators.find((item) => item.username === username || item.provider_creator_id === username);
    if (!creator) return;
    videosByCreator[creator.provider_creator_id] = videos.slice(0, 20).map((video) => ({
      ...video,
      provider: "creator_provided",
      provider_creator_id: creator.provider_creator_id,
      creator_username: creator.username,
      source_type: "creator_provided",
      source_risk_level: "low",
    }));
  });
  return {
    status: "local_preview_normalized",
    provider: "creator_provided",
    mode: "preview",
    source_type: "creator_provided",
    creator_count: creators.length,
    video_count: Object.values(videosByCreator).reduce((sum, items) => sum + items.length, 0),
    creators,
    videos_by_creator: videosByCreator,
  };
}

// Route the normalized run into the standard intake state so the existing
// quality gate, screening, and gated import buttons all apply unchanged.
function applyCreatorProvidedToIntake(response) {
  applyProviderRunToPreview(response);
  const creators = (response.creators || []).map(normalizeProviderCreator);
  if (!creators.length) return;
  state.intakeCreators = creators;
  state.intakeCreatorHeaders = Object.keys(creators[0]);
  creators.forEach((creator) => {
    const posts = state.recentPostsByCreator[creator.creator_id];
    if (posts?.length) {
      state.recentPostHeadersByCreator[creator.creator_id] = Object.keys(posts[0]);
    }
  });
}

// --- Market news signals (slimmed-C step (b): public Google News RSS panel) ---
// Market signals only — these rows never become creator workflow inputs.

function selectedDiscoveryCountries() {
  const select = byId("discoveryCountries");
  const chosen = select
    ? Array.from(select.selectedOptions).map((option) => option.value)
    : [];
  return chosen.length ? chosen : ["MX", "PE", "EC"];
}

async function loadNewsSignals() {
  const countries = selectedDiscoveryCountries();
  const productCategories = [byId("discoveryProduct")?.value || "sunscreen"];
  try {
    const response = await window.BriwellApi.fetchNewsSignals({
      countries,
      productCategories,
      maxItemsPerQuery: 5,
    });
    state.newsSignals = response;
    renderNewsSignals();
    showToast(
      response.mode === "live"
        ? `뉴스 신호 ${response.item_count || 0}건 (라이브)`
        : `뉴스 신호 샘플 ${response.item_count || 0}건 (드라이런)`
    );
  } catch (error) {
    if (error.payload) {
      state.newsSignals = error.payload;
      renderNewsSignals();
      return;
    }
    state.newsSignals = buildLocalNewsSignals(countries, productCategories);
    renderNewsSignals();
    showToast("뉴스 신호 미리보기 · API 오프라인");
  }
}

// Mirrors the server dry-run shape so the offline panel is clearly labeled
// sample data rather than pretending headlines were fetched.
function buildLocalNewsSignals(countries, productCategories) {
  const marketNames = { MX: "Mexico", PE: "Peru", EC: "Ecuador" };
  const items = countries.flatMap((country) => [
    {
      title: `[샘플] Tendencias K-beauty en ${marketNames[country] || country}: rutinas coreanas en alza`,
      url: "https://news.google.com/",
      source: "로컬 미리보기 샘플",
      published_at: null,
      country,
      product_category: productCategories[0] || "sunscreen",
      query: `k-beauty ${marketNames[country] || country}`,
    },
  ]);
  return {
    status: "local_preview",
    mode: "preview",
    source_type: "public_news_rss",
    item_count: items.length,
    query_count: countries.length,
    items,
    live_blockers: ["API offline"],
    errors: [],
  };
}

function renderNewsSignals() {
  const meta = byId("newsSignalsMeta");
  const list = byId("newsSignalsList");
  if (!meta || !list) return;
  const signals = state.newsSignals;
  if (!signals) {
    meta.innerHTML = "";
    list.innerHTML = `<p class="muted">뉴스 신호를 불러오면 시장 헤드라인이 표시됩니다.</p>`;
    return;
  }

  const modeBadge =
    signals.mode === "live"
      ? '<span class="badge green">라이브 RSS</span>'
      : signals.mode === "dry_run"
        ? '<span class="badge amber">드라이런 샘플</span>'
        : '<span class="badge amber">라이브 아님 · 미리보기/오류</span>';
  const blockerNote = (signals.live_blockers || []).length
    ? `<span class="muted">라이브 게이트: ${escapeHtml((signals.live_blockers || []).join(" · "))}</span>`
    : "";
  meta.innerHTML = `
    <div class="news-signal-summary">
      ${modeBadge}
      <span>쿼리 ${escapeHtml(String(signals.query_count ?? 0))}개 · 헤드라인 ${escapeHtml(String(signals.item_count ?? 0))}건</span>
      ${blockerNote}
    </div>
  `;

  const items = signals.items || [];
  if (!items.length) {
    list.innerHTML = `<p class="muted">표시할 헤드라인이 없습니다${
      (signals.errors || []).length ? ` · 오류 ${signals.errors.length}건` : ""
    }.</p>`;
    return;
  }
  list.innerHTML = items
    .map(
      (item) => `
      <article class="news-signal-item">
        <a href="${escapeHtml(safeExternalUrl(item.url))}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>
        <small>
          <span class="badge blue">${escapeHtml(formatMarket(item.country))}</span>
          ${escapeHtml(item.source || "출처 미상")}${item.published_at ? ` · ${escapeHtml(item.published_at)}` : ""}
          · ${escapeHtml(item.query || "")}
        </small>
      </article>
    `
    )
    .join("");
}

// Feed URLs are external input: only allow http(s) link targets so a hostile
// RSS entry can never smuggle a javascript:/data: href into the panel.
function safeExternalUrl(url) {
  const text = String(url || "").trim();
  return /^https?:\/\//i.test(text) ? text : "#";
}

async function runRecentScreenForCreator(creatorId) {
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  const posts = (state.recentPostsByCreator[creatorId] || []).slice(0, 20);
  const mode = byId("recentScreenMode")?.value || "dry_run";
  const liveGemini = mode === "live";
  if (!creator) return;
  if (liveGemini && !state.aiProvider?.live_ready) {
    showResult("postImportResult", {
      status: "live_gemini_unavailable",
      message: "Live Gemini requires API online, AI_DRY_RUN=false, ALLOW_LIVE_PROVIDER_CALLS=true, and GEMINI_API_KEY.",
      provider: state.aiProvider,
    });
    showToast("라이브 Gemini 미준비 · 드라이런 미리보기 사용");
    byId("recentScreenMode").value = "dry_run";
    localStorage.setItem("briwell.recentScreenMode", "dry_run");
    return;
  }

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
    dry_run: !liveGemini,
    allow_live_provider_calls: liveGemini,
    persist_result: looksLikeUuid(creatorId),
  };

  try {
    const response = await window.BriwellApi.runRecentPostsScreen(payload);
    const providerOutput = extractRecentScreenOutput(response);
    const output = providerOutput || previewRecentPostsScreen(creator, posts);
    state.recentScreenResults[creatorId] = output;
    applyScreenResultToCreator(creatorId, output);
    showResult("postImportResult", {
      status: providerOutput
        ? (liveGemini ? "live_gemini_screened" : "dry_run_screened")
        : (liveGemini ? "live_gemini_failed_preview_only" : "local_preview_screened"),
      creator_id: creatorId,
      output,
      provider_result: providerOutput ? undefined : response.result,
      invocation_log: response.invocation_log,
      screen_persistence_status: response.screen_persistence_status,
      screen_persistence_error: response.screen_persistence_error,
    });
  } catch (error) {
    if (!error.cancelled) {
      const output = extractRecentScreenOutput(error.payload) || previewRecentPostsScreen(creator, posts);
      state.recentScreenResults[creatorId] = output;
      applyScreenResultToCreator(creatorId, output);
    }
    showResult("postImportResult", error.payload || { status: "local_preview_screened", creator_id: creatorId, output: state.recentScreenResults[creatorId] });
    if (error.cancelled) {
      renderAll();
      showToast("취소됨 · 아무것도 기록되지 않음");
      return;
    }
  }
  renderAll();
  document.querySelector('[data-view="intake"]').click();
  showToast(`@${creator.username} 최근 20개 스크리닝 완료`);
}

const OPERATIONS_PIPELINE_STEP_COUNT = 8;

// The pipeline fires up to OPERATIONS_PIPELINE_STEP_COUNT sequential writes.
// Gating each one individually would show the live-write confirm modal
// repeatedly (modal fatigue) and, worse, a "cancel" on any single step used
// to have no effect on the rest of the run. Instead we ask for confirmation
// once up front for the whole pipeline, grant a short-lived approval token
// that writeGate honors only for calls made during this run, and stop the
// run immediately if the operator declines or any step still comes back
// cancelled.
let pipelineWriteApprovalActive = false;

async function confirmOperationsPipelineWrite() {
  // Same fail-closed rule as writeGate: while connectivity is still unknown,
  // never assume preview. Once it's known, skip the modal only if we're
  // actually offline (nothing will be written) or the operator has already
  // suppressed confirmations this session.
  if (state.apiConnectivityChecked && !state.apiOnline) return true;
  if (state.apiConnectivityChecked && isWriteConfirmSuppressed()) return true;
  return openWriteConfirmModal({
    path: `운영 파이프라인 (최대 ${OPERATIONS_PIPELINE_STEP_COUNT}단계 실행)`,
    method: "POST",
    apiBase: window.BriwellApi.readConfig().apiBase,
  });
}

async function runOperationsPipeline() {
  const approved = await confirmOperationsPipelineWrite();
  if (!approved) {
    state.operationsPipeline = {
      status: "cancelled_by_user",
      api_status: "cancelled_by_user",
    };
    renderOperationsPipelineSummary();
    showResult("operationsEngineResult", state.operationsPipeline);
    showToast("운영 파이프라인 취소됨");
    return;
  }

  pipelineWriteApprovalActive = true;
  try {
    await executeOperationsPipelineSteps();
  } finally {
    pipelineWriteApprovalActive = false;
  }
}

// Returns true (and renders the partial results collected so far) if any of
// the given step results came back cancelled_by_user, so the caller can bail
// out of the pipeline immediately instead of continuing to prompt/execute
// subsequent steps.
function stopOperationsPipelineOnCancel(stepsSoFar) {
  const cancelledStep = Object.values(stepsSoFar).find(
    (step) => step && step.api_status === "cancelled_by_user"
  );
  if (!cancelledStep) return false;
  state.operationsPipeline = {
    ...stepsSoFar,
    status: "cancelled_by_user",
    api_status: "cancelled_by_user",
  };
  renderOperationsPipelineSummary();
  showResult("operationsEngineResult", state.operationsPipeline);
  showToast("운영 파이프라인 취소됨");
  return true;
}

async function executeOperationsPipelineSteps() {
  const creators = state.creators.map(toOperationCreator);
  const recentPostsByCreator = operationRecentPostsByCreator();
  const screenResults = ensureOperationScreenResults();
  const qualityGate = evaluateImportQuality();
  const campaignProduct = byId("campaignProduct")?.value || "sunscreen";
  const campaignCountry = byId("campaignCountry")?.value || "MX";
  const persistEntityResults = canPersistOperationCreators(creators);

  const acquisition = await callOperationStep(
    () =>
      window.BriwellApi.runAcquisitionOrchestration({
        source_type: "manual",
        source_risk_level: "low",
        product_category: campaignProduct,
        product_name: "Briwell Daily Sun",
        country: campaignCountry,
        campaign_id: byId("campaignName")?.value || "campaign-1",
        campaign_goal: byId("campaignGoal")?.value || "",
        upload_name: "dashboard_current_pool",
        creator_candidates: creators,
        recent_posts_by_creator: recentPostsByCreator,
        persist_imports: persistEntityResults,
        run_recent_20_screen: true,
        recent_screen_dry_run: true,
        persist_recent_screen_results: persistEntityResults,
        run_campaign_match: true,
        build_outreach_plan: true,
        dm_variant: "product_review",
        min_score: 70,
        max_risk_penalty: 12,
        spend_usd: Number(byId("campaignBudget")?.value || 0),
        performance_snapshots: buildOperationPerformanceSnapshots(creators),
      }),
    {
      status: "local_preview",
      mode: "offline_ready_no_paid_provider_benchmark",
      quality_gate: qualityGate,
      next_actions: ["API offline; local pipeline steps continue below."],
    }
  );
  if (stopOperationsPipelineOnCancel({ acquisition })) return;

  const importQuality = await callOperationStep(
    () =>
      window.BriwellApi.saveImportQualityLog({
        dataset_type: "mixed",
        upload_name: "dashboard_current_pool",
        source_type: "manual",
        source_risk_level: "low",
        creator_candidates: creators,
        recent_posts_by_creator: recentPostsByCreator,
        quality_gate: qualityGate,
      }),
    {
      status: "logged",
      persistence_status: "local_preview",
      quality_gate: qualityGate,
      next_action: qualityGate.overall_status === "ready" ? "run_creator_enrichment" : "operator_review",
    }
  );
  if (stopOperationsPipelineOnCancel({ acquisition, importQuality })) return;

  const enrichment = await callOperationStep(
    () =>
      window.BriwellApi.enrichCreators({
        source_risk_level: "low",
        creators,
        persist_result: persistEntityResults,
      }),
    {
      status: "enriched",
      persistence_status: "local_preview",
      items: creators.map(localEnrichmentFromCreator),
      summary: {
        ready: creators.length,
        needs_review: 0,
        blocked: 0,
      },
    }
  );
  if (stopOperationsPipelineOnCancel({ acquisition, importQuality, enrichment })) return;

  const recentApply = await callOperationStep(
    () =>
      window.BriwellApi.applyRecentPostsResults({
        source_risk_level: "low",
        items: creators.map((creator) => ({
          creator_id: creator.creator_id,
          creator_snapshot: creator,
          screen_result: screenResults[creator.creator_id],
        })),
        persist_result: persistEntityResults,
      }),
    localRecentApply(creators, screenResults)
  );
  if (stopOperationsPipelineOnCancel({ acquisition, importQuality, enrichment, recentApply })) return;

  const match = await callOperationStep(
    () =>
      window.BriwellApi.matchCampaignCandidates({
        campaign_id: byId("campaignName")?.value || "campaign-1",
        country: campaignCountry,
        product_category: campaignProduct,
        campaign_goal: byId("campaignGoal")?.value || "",
        candidates: creators,
        recent_screen_results: screenResults,
        min_score: 70,
        max_risk_penalty: 12,
        limit: 20,
      }),
    localCampaignMatch(creators, screenResults, campaignProduct, campaignCountry)
  );
  if (stopOperationsPipelineOnCancel({ acquisition, importQuality, enrichment, recentApply, match })) return;

  const matchedItems = match.items || [];
  const outreachPlan = await callOperationStep(
    () =>
      window.BriwellApi.createOutreachPlan({
        campaign_id: "campaign-1",
        product_category: campaignProduct,
        product_name: "Briwell Daily Sun",
        dm_variant: "product_review",
        candidates: matchedItems,
        persist_result: false,
      }),
    localOutreachPlan(matchedItems, campaignProduct)
  );
  if (
    stopOperationsPipelineOnCancel({
      acquisition,
      importQuality,
      enrichment,
      recentApply,
      match,
      outreachPlan,
    })
  )
    return;

  const crm = await callOperationStep(
    () =>
      window.BriwellApi.buildOutreachCrmBoard({
        campaign_id: "campaign-1",
        outreach_items: outreachPlan.items || [],
        persist_event: false,
      }),
    localCrmBoard(outreachPlan.items || [])
  );
  if (
    stopOperationsPipelineOnCancel({
      acquisition,
      importQuality,
      enrichment,
      recentApply,
      match,
      outreachPlan,
      crm,
    })
  )
    return;

  const performance = await callOperationStep(
    () =>
      window.BriwellApi.createPerformanceRollup({
        campaign_id: "campaign-1",
        spend_usd: Number(byId("campaignBudget")?.value || 0),
        snapshots: buildOperationPerformanceSnapshots(matchedItems),
      }),
    localPerformanceRollup(matchedItems)
  );
  if (
    stopOperationsPipelineOnCancel({
      acquisition,
      importQuality,
      enrichment,
      recentApply,
      match,
      outreachPlan,
      crm,
      performance,
    })
  )
    return;

  state.operationsPipeline = {
    acquisition,
    importQuality,
    enrichment,
    recentApply,
    match,
    outreachPlan,
    crm,
    performance,
  };
  renderOperationsPipelineSummary();
  showResult("operationsEngineResult", state.operationsPipeline);
  showToast("운영 파이프라인 완료");
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
    showResult("campaignSaveResult", error.payload || { status: "local_preview_saved", campaign: payload });
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
    showResult("draftResult", error.payload || { status: "local_preview_prepared", prepared_count: selected.length });
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
    showResult("claimsResult", error.payload || { status: "local_preview_passed", safe_to_send: true });
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
    showResult("manualSendResult", error.payload || { status: "local_preview_recorded", next_status: "dm_sent" });
  }
}

function readSnapshotRevenueTriple() {
  const currency = byId("snapshotCurrency")?.value || "USD";
  const amount = Number(byId("snapshotRevenue").value || 0);
  const fxRate = currency === "USD" ? 1 : Number(byId("snapshotFxRate")?.value || 0);
  return { currency, amount, fxRate };
}

function updateSnapshotFxAvailability() {
  const currencySelect = byId("snapshotCurrency");
  const fxInput = byId("snapshotFxRate");
  if (!currencySelect || !fxInput) return;
  const isUsd = currencySelect.value === "USD";
  fxInput.disabled = isUsd;
  if (isUsd) fxInput.value = "1";
}

async function saveSnapshot() {
  const revenue = readSnapshotRevenueTriple();
  if (revenue.currency !== "USD" && !(revenue.fxRate > 0)) {
    showToast("MXN/PEN 매출은 기록시점 USD 환율이 필요합니다");
    return;
  }
  const payload = {
    campaign_id: byId("snapshotCampaign").value.trim(),
    creator_id: byId("snapshotCreator").value.trim(),
    post_url: byId("snapshotPostUrl").value.trim(),
    coupon_code: byId("snapshotCoupon").value.trim(),
    view_count: Number(byId("snapshotViews").value || 0),
    revenue_amount: revenue.amount,
    revenue_currency: revenue.currency,
    fx_rate_usd: revenue.fxRate,
    source_type: "manual",
    source_risk_level: "low",
  };
  const revenueUsd = revenue.amount * revenue.fxRate;
  try {
    const response = await window.BriwellApi.savePerformanceSnapshot(payload);
    showResult("snapshotResult", response);
    recordSessionSnapshot(payload, revenueUsd, response.status === "persisted" ? "live" : "preview");
  } catch (error) {
    if (error.cancelled) {
      showResult("snapshotResult", error.payload);
      return;
    }
    showResult("snapshotResult", error.payload || { status: "local_preview_saved", snapshot: payload });
    // Only the offline preview fallback counts as recorded; an API rejection payload
    // (e.g. 422 currency/FX validation) means nothing was stored anywhere.
    if (!error.payload) recordSessionSnapshot(payload, revenueUsd, "preview");
  }
}

function recordSessionSnapshot(payload, revenueUsd, recorded) {
  state.sessionSnapshots.push({
    view_count: payload.view_count,
    revenue_usd: revenueUsd,
    recorded,
  });
  renderScreenKpis();
}

async function issueDiscountCode() {
  const payload = {
    creator_id: byId("issueCreatorId").value.trim(),
    campaign_id: byId("issueCampaignId").value.trim() || null,
    code: byId("issueCode").value.trim(),
    commission_rate: Number(byId("issueCommissionRate").value || 0),
    customer_discount_percent: Number(byId("issueDiscountPercent").value || 0),
  };
  if (!payload.creator_id || payload.code.length < 3) {
    showToast("크리에이터 ID와 3자 이상 할인코드가 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.issueDiscountCode(payload);
    showResult("issueDiscountResult", response);
    if (response.status === "dry_run") {
      showToast("드라이런 · Shopify에 실제 생성되지 않음");
      recordSessionDiscountCode("dry_run");
    } else {
      showToast(`할인코드 ${response.discount_code?.code || payload.code} 발급 완료`);
      recordSessionDiscountCode("live");
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("issueDiscountResult", error.payload);
      return;
    }
    showResult("issueDiscountResult", error.payload || { status: "local_preview_saved", discount_code: payload });
    if (!error.payload) recordSessionDiscountCode("preview");
  }
}

function recordSessionDiscountCode(mode) {
  state.sessionDiscountCodes.push({ mode });
  renderScreenKpis();
}

async function issuePortalToken() {
  const creatorId = byId("portalCreatorId").value.trim();
  if (!creatorId) {
    showToast("크리에이터 ID가 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.issuePortalToken({ creator_id: creatorId });
    showResult("portalTokenResult", response);
    if (response.status === "persisted") {
      appendPortalLinkRow(response.token);
      showToast("포털 링크 발급 완료 · 이전 링크는 즉시 무효");
    } else if (response.status === "validated_not_persisted") {
      appendPortalLinkNote("이 토큰은 DB에 저장되지 않아 실제 포털 링크로 동작하지 않습니다.");
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("portalTokenResult", error.payload);
      return;
    }
    // A portal token only exists if the server stored it — fabricating one
    // locally would hand the operator a dead link, so there is no offline
    // preview fallback on this panel.
    showResult(
      "portalTokenResult",
      error.payload || {
        status: "api_unreachable",
        message: "포털 토큰은 서버에서만 발급됩니다. API 연결 후 다시 시도하세요.",
      }
    );
  }
}

async function revokePortalTokens() {
  const creatorId = byId("portalCreatorId").value.trim();
  if (!creatorId) {
    showToast("크리에이터 ID가 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.revokePortalTokens(creatorId);
    showResult("portalTokenResult", response);
    if (response.status === "persisted") {
      showToast(`포털 링크 ${response.revoked ?? 0}건 폐기 · 기존 링크 즉시 무효`);
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("portalTokenResult", error.payload);
      return;
    }
    showResult(
      "portalTokenResult",
      error.payload || {
        status: "api_unreachable",
        message: "포털 토큰 폐기는 서버에서만 수행됩니다. API 연결 후 다시 시도하세요.",
      }
    );
  }
}

function appendPortalLinkRow(
  token,
  resultId = "portalTokenResult",
  baseInputId = "portalPageBase",
  linkLabel = "크리에이터 포털 개인 링크"
) {
  const box = byId(resultId);
  const base = byId(baseInputId).value.trim();
  const link = base ? `${base}${base.includes("?") ? "&" : "?"}t=${encodeURIComponent(token)}` : "";
  const row = document.createElement("div");
  row.className = "portal-link-row";
  const input = document.createElement("input");
  input.readOnly = true;
  input.value = link || token;
  input.setAttribute("aria-label", link ? linkLabel : "접근 토큰");
  const copyButton = document.createElement("button");
  copyButton.type = "button";
  copyButton.className = "button";
  copyButton.textContent = link ? "링크 복사" : "토큰 복사";
  copyButton.addEventListener("click", () => copyPortalLink(input));
  row.appendChild(input);
  row.appendChild(copyButton);
  box.appendChild(row);
  if (!base) {
    appendPortalLinkNote(
      "페이지 주소를 입력하면 완성된 개인 링크로 복사할 수 있습니다.",
      resultId
    );
  }
}

function appendPortalLinkNote(text, resultId = "portalTokenResult") {
  const note = document.createElement("p");
  note.className = "portal-link-note";
  note.textContent = text;
  byId(resultId).appendChild(note);
}

function copyPortalLink(input) {
  const done = () => showToast("복사됨 · 해당 상대에게만 전달하세요");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(input.value).then(done, () => fallbackCopy(input, done));
  } else {
    fallbackCopy(input, done);
  }
}

// --- Brand Partner Hub (operator side) --------------------------------------

async function createPartner() {
  const payload = {
    company_name: byId("partnerCompanyName").value.trim(),
    contact_name: byId("partnerContactName").value.trim() || null,
    contact_email: byId("partnerContactEmail").value.trim() || null,
    internal_memo: byId("partnerInternalMemo").value.trim() || null,
  };
  if (!payload.company_name) {
    showToast("회사명이 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.createPartner(payload);
    showResult("createPartnerResult", response);
    if (response.status === "persisted") {
      showToast(`파트너 ${payload.company_name} 등록 완료`);
      if (response.partner?.id) byId("hubPartnerId").value = response.partner.id;
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("createPartnerResult", error.payload);
      return;
    }
    showResult(
      "createPartnerResult",
      error.payload || {
        status: "api_unreachable",
        message: "파트너 등록은 서버에서만 수행됩니다. API 연결 후 다시 시도하세요.",
      }
    );
  }
}

async function issueHubToken() {
  const partnerId = byId("hubPartnerId").value.trim();
  if (!partnerId) {
    showToast("파트너 ID가 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.issueHubToken({ partner_id: partnerId });
    showResult("hubTokenResult", response);
    if (response.status === "persisted") {
      appendPortalLinkRow(response.token, "hubTokenResult", "hubPageBase", "브랜드 파트너 허브 링크");
      showToast("허브 링크 발급 완료 · 이전 링크는 즉시 무효");
    } else if (response.status === "validated_not_persisted") {
      appendPortalLinkNote(
        "이 토큰은 DB에 저장되지 않아 실제 허브 링크로 동작하지 않습니다.",
        "hubTokenResult"
      );
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("hubTokenResult", error.payload);
      return;
    }
    showResult(
      "hubTokenResult",
      error.payload || {
        status: "api_unreachable",
        message: "허브 토큰은 서버에서만 발급됩니다. API 연결 후 다시 시도하세요.",
      }
    );
  }
}

async function revokeHubTokens() {
  const partnerId = byId("hubPartnerId").value.trim();
  if (!partnerId) {
    showToast("파트너 ID가 필요합니다");
    return;
  }
  try {
    const response = await window.BriwellApi.revokeHubTokens(partnerId);
    showResult("hubTokenResult", response);
    if (response.status === "persisted") {
      showToast(`허브 링크 ${response.revoked ?? 0}건 폐기 · 기존 링크 즉시 무효`);
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("hubTokenResult", error.payload);
      return;
    }
    showResult(
      "hubTokenResult",
      error.payload || {
        status: "api_unreachable",
        message: "허브 토큰 폐기는 서버에서만 수행됩니다. API 연결 후 다시 시도하세요.",
      }
    );
  }
}

const HUB_GRADE_LABELS = {
  no_flag: "신호 없음",
  restricted_candidate: "제한 후보",
  blocked_candidate: "금지 후보",
};

function worstRegulatoryGrade(regulatoryFlags) {
  const grades = Object.values(regulatoryFlags?.by_country || {}).map((entry) => entry.grade);
  if (grades.includes("blocked_candidate")) return "blocked_candidate";
  if (grades.includes("restricted_candidate")) return "restricted_candidate";
  if (grades.length) return "no_flag";
  return null;
}

async function loadPartnerReviewQueue() {
  const mount = byId("reviewQueueTable");
  mount.innerHTML = '<tr><td colspan="7" class="muted">불러오는 중…</td></tr>';
  try {
    const response = await window.BriwellApi.fetchPartnerReviewQueue();
    renderPartnerReviewQueue(response.items || []);
  } catch (error) {
    mount.innerHTML = `<tr><td colspan="7" class="muted">${escapeHtml(
      error.payload?.detail?.message || "검수 큐를 불러오지 못했습니다 — API 연결을 확인하세요."
    )}</td></tr>`;
  }
}

function renderPartnerReviewQueue(items) {
  const mount = byId("reviewQueueTable");
  if (!items.length) {
    mount.innerHTML =
      '<tr><td colspan="7" class="muted">검수 대기 초안이 없습니다 — 파트너 제출을 기다리는 중.</td></tr>';
    return;
  }
  mount.innerHTML = items
    .map((item) => {
      const draft = item.draft || {};
      const score = item.completeness?.score;
      const grade = worstRegulatoryGrade(item.regulatory_flags);
      const when = item.updated_at ? String(item.updated_at).slice(0, 10) : "—";
      return `<tr data-draft-id="${escapeHtml(item.draft_id)}">
        <td><button class="button" data-pick-draft="${escapeHtml(item.draft_id)}">선택</button></td>
        <td>${escapeHtml(item.company_name || "—")}</td>
        <td>${escapeHtml(draft.product_name || "(제품명 없음)")}</td>
        <td>${escapeHtml(draft.product_category || "—")}</td>
        <td>${typeof score === "number" ? `${score}/100` : "—"}</td>
        <td>${grade ? escapeHtml(HUB_GRADE_LABELS[grade] || grade) : "—"}</td>
        <td>${escapeHtml(when)}</td>
      </tr>`;
    })
    .join("");
  mount.querySelectorAll("[data-pick-draft]").forEach((button) => {
    button.addEventListener("click", () => {
      byId("reviewDraftId").value = button.getAttribute("data-pick-draft");
      mount.querySelectorAll("tr").forEach((row) => row.classList.remove("row-selected"));
      button.closest("tr")?.classList.add("row-selected");
    });
  });
}

async function reviewPartnerDraft(decision) {
  const draftId = byId("reviewDraftId").value.trim();
  if (!draftId) {
    showToast("검수 큐에서 초안을 먼저 선택하세요");
    return;
  }
  const payload = { decision, reason: byId("reviewReason").value.trim() || null };
  try {
    const response = await window.BriwellApi.reviewPartnerDraft(draftId, payload);
    showResult("reviewDraftResult", response);
    if (response.status === "persisted") {
      showToast(
        decision === "approved"
          ? "승인 완료 · 제품 카탈로그에 등록됨"
          : "반려 완료 · 파트너 허브에 반영됨"
      );
      byId("reviewDraftId").value = "";
      loadPartnerReviewQueue();
    }
  } catch (error) {
    if (error.cancelled) {
      showResult("reviewDraftResult", error.payload);
      return;
    }
    showResult(
      "reviewDraftResult",
      error.payload || {
        status: "api_unreachable",
        message: "검수 결정은 서버에서만 기록됩니다. API 연결 후 다시 시도하세요.",
      }
    );
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
    const response = await window.BriwellApi.saveContract(payload);
    showResult("contractResult", response);
    recordSessionContract(payload, response.status === "persisted" ? "live" : "preview");
  } catch (error) {
    if (error.cancelled) {
      showResult("contractResult", error.payload);
      return;
    }
    showResult("contractResult", error.payload || { status: "local_preview_saved", contract: payload });
    if (!error.payload) recordSessionContract(payload, "preview");
  }
}

function recordSessionContract(payload, recorded) {
  state.sessionContracts.push({
    fee_usd: payload.compensation_terms?.fee_usd || 0,
    recorded,
  });
  renderScreenKpis();
}

function buildPreviewDiscoveryRows(countries, product, platform, limit) {
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

function buildLocalKeywordPlaybook(countries, product, limit) {
  const bank = {
    sunscreen: [
      ["trend", "spf coreano viral tiktok"],
      ["discovery", "protector solar coreano"],
      ["concern", "bloqueador coreano sin grasa"],
      ["format", "grwm protector solar coreano"],
      ["commerce", "donde comprar protector solar coreano"],
    ],
    calming_serum: [
      ["trend", "serum coreano viral tiktok"],
      ["discovery", "serum calmante coreano"],
      ["concern", "barrera de la piel serum"],
      ["format", "probando serum coreano"],
      ["commerce", "serum coreano recomendado"],
    ],
    cleanser: [
      ["trend", "limpiador coreano viral tiktok"],
      ["discovery", "limpiador facial coreano"],
      ["concern", "limpiador para piel grasa coreano"],
      ["format", "doble limpieza coreana rutina"],
      ["commerce", "limpiador coreano recomendado"],
    ],
    sheet_mask: [
      ["trend", "mascarilla coreana viral tiktok"],
      ["discovery", "mascarilla facial coreana"],
      ["concern", "mascarilla hidratante coreana"],
      ["format", "selfcare mascarilla coreana"],
      ["commerce", "kbeauty barato mascarillas"],
    ],
    cushion_foundation: [
      ["trend", "cushion coreano viral tiktok"],
      ["discovery", "cushion coreano"],
      ["concern", "base ligera para diario"],
      ["format", "glass skin maquillaje"],
      ["commerce", "dupes maquillaje coreano"],
    ],
  };
  const countryNames = { MX: "mexico", PE: "peru", EC: "ecuador" };
  const items = countries.flatMap((country) =>
    (bank[product] || bank.sunscreen).slice(0, limit).map(([intent, query]) => ({
      country,
      product_category: product,
      intent_type: intent,
      query: `${query} ${countryNames[country] || ""}`.trim(),
      query_type: "keyword",
      audience: intent === "trend" || intent === "format" ? "gen_z" : "young_millennial",
    }))
  );
  return {
    status: "local_keyword_preview",
    strategy: "latam_kbeauty_20s_30s",
    keyword_count: items.length,
    items,
  };
}

function buildPreviewCoverageAudit(countries, product, limit) {
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

function buildPreviewRecallSafeguards() {
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
      showToast(`@${creator?.username || "creator"} 캠페인 검토 숏리스트 추가`);
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
    creator_id: creator.id || creator.creator_id || stableCreatorId(creator.username || "creator"),
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
    source_type: normalizeSourceType(creator.source_type || "manual"),
    source_risk_level: creator.source_risk_level || "low",
    final_score: toNumber(creator.final_score || creator.score || 70),
    risk_penalty: toNumber(creator.risk_penalty || 5),
    segment: creator.segment || "review_creator",
    signals: creator.signals || creator.recommended_products || ["Profile"],
    recommended_products: creator.recommended_products || [],
    recommended_campaign_angle: creator.recommended_campaign_angle || "",
  };
}

function normalizeProviderCreator(creator) {
  const isCreatorProvided = creator.provider === "creator_provided" || creator.source_type === "creator_provided";
  return normalizeApiCreator({
    ...creator,
    id: creator.creator_id || creator.provider_creator_id || stableCreatorId(creator.username || "creator"),
    creator_id: creator.creator_id || creator.provider_creator_id || stableCreatorId(creator.username || "creator"),
    username: creator.username,
    display_name: creator.display_name,
    country: creator.country,
    profile_url: creator.profile_url,
    profile_image_url: creator.profile_image_url,
    follower_count: creator.follower_count,
    avg_views: creator.avg_views,
    engagement_rate: creator.engagement_rate,
    platform: creator.platform || platformFromProfileUrl(creator.profile_url),
    source_type: creator.source_type || "approved_provider",
    source_risk_level: creator.source_risk_level || "low_medium",
    final_score: providerPreviewScore(creator),
    risk_penalty: creator.source_risk_level === "low" ? 3 : 6,
    segment: isCreatorProvided ? "creator_submitted" : "provider_discovered",
    signals:
      creator.kbeauty_fit_signals ||
      (Array.isArray(creator.signals) && creator.signals.length ? creator.signals : [creator.matched_intent || "provider"]),
    recommended_products: [creator.product_category].filter(Boolean),
    recommended_campaign_angle: isCreatorProvided
      ? "크리에이터 본인 제공 데이터(동의 확보) 기반 후보 — 최근 20개 스크리닝으로 검증 필요"
      : `${formatProductCategory(creator.product_category)} creator found through ${creator.provider || "provider"} query "${creator.matched_query || ""}".`,
  });
}

function platformFromProfileUrl(url) {
  const text = String(url || "").toLowerCase();
  if (text.includes("instagram.com")) return "instagram";
  if (text.includes("youtube.com") || text.includes("youtu.be")) return "youtube";
  return "tiktok";
}

function normalizeProviderVideo(video, creatorId) {
  return {
    creator_id: creatorId,
    video_id: video.platform_video_id || video.url,
    platform_video_id: video.platform_video_id || "",
    url: video.url,
    caption: video.caption || "",
    transcript: video.transcript || "",
    hashtags: video.hashtags || [],
    posted_at: normalizeDate(video.posted_at),
    view_count: toNumber(video.view_count),
    like_count: toNumber(video.like_count),
    comment_count: toNumber(video.comment_count),
    share_count: toNumber(video.share_count),
    save_count: toNumber(video.save_count),
    duration_seconds: toNumber(video.duration_seconds),
    thumbnail_url: video.thumbnail_url || "",
    source_type: video.source_type || "approved_provider",
    source_risk_level: video.source_risk_level || "low_medium",
    source_url: video.url,
  };
}

function providerPreviewScore(creator) {
  const signals = creator.kbeauty_fit_signals || [];
  const base = 72 + Math.min(12, signals.length * 3);
  const engagementBonus = Math.min(8, Math.round(toNumber(creator.engagement_rate) || 0));
  const audienceBonus = creator.audience_age_fit === "both" ? 4 : 6;
  return Math.min(96, base + engagementBonus + audienceBonus);
}

function normalizeCsvCreator(row, index) {
  const username = String(row.username || row.handle || row.account || `creator_${index + 1}`).replace(/^@/, "").trim();
  return normalizeApiCreator({
    creator_id: row.creator_id || stableCreatorId(username),
    username,
    display_name: row.display_name || row.name || username,
    country: normalizeCountry(row.country || row.market),
    profile_url: row.profile_url || row.url || `https://www.tiktok.com/@${username}`,
    bio: row.bio || "",
    follower_count: row.follower_count || row.followers || 0,
    avg_views: row.avg_views || row.average_views || 0,
    engagement_rate: row.engagement_rate || row.er || 0,
    platform: row.platform || "tiktok",
    source_type: normalizeSourceType(row.source_type || "manual"),
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
    url: row.url || row.post_url || `https://www.tiktok.com/@${creatorId}/video/${index + 1}`,
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
    source_type: normalizeSourceType(row.source_type || "manual"),
    source_risk_level: normalizeRisk(row.source_risk_level || row.risk || "low"),
    source_url: row.source_url || row.url || row.post_url || "",
  };
}

function toCreatorImportItem(creator) {
  return {
    country: creator.country,
    username: creator.username,
    profile_url: creator.profile_url || `https://www.tiktok.com/@${creator.username}`,
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
    raw_metadata: {
      manual_import: true,
      source: "dashboard_talent_intake",
      row_source_type: normalizeSourceType(post.source_type || "manual"),
      row_source_risk_level: normalizeRisk(post.source_risk_level || "low"),
    },
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

function previewRecentPostsScreen(creator, posts) {
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

async function callOperationStep(remoteCall, fallback) {
  try {
    const response = await remoteCall();
    return {
      ...response,
      api_status: "live",
    };
  } catch (error) {
    if (error.cancelled) {
      return {
        status: "cancelled_by_user",
        api_status: "cancelled_by_user",
        api_error: summarizeApiError(error),
      };
    }
    return {
      ...fallback,
      api_status: "local_preview",
      api_error: summarizeApiError(error),
    };
  }
}

function summarizeApiError(error) {
  const detail = error?.payload?.detail;
  if (typeof detail?.message === "string") return detail.message;
  if (typeof detail?.code === "string") return detail.code;
  if (typeof error?.message === "string") return error.message;
  return "API request failed; local preview data used.";
}

function toOperationCreator(creator) {
  return {
    creator_id: creator.creator_id,
    country: creator.country,
    username: creator.username,
    display_name: creator.display_name,
    profile_url: creator.profile_url || `https://www.tiktok.com/@${creator.username}`,
    source_risk_level: sourceRiskForCreator(creator.creator_id),
    bio: creator.bio || creator.recommended_campaign_angle || "",
    language: "es",
    platform: creator.platform || "tiktok",
    follower_count: toNumber(creator.follower_count),
    avg_views: toNumber(creator.avg_views),
    engagement_rate: toNumber(creator.engagement_rate),
    contact_email: creator.contact_email || null,
    instagram_url: creator.instagram_url || null,
    status: creator.status || "active",
    final_score: toNumber(creator.final_score),
    risk_penalty: toNumber(creator.risk_penalty),
    segment: creator.segment || "review_creator",
    signals: creator.signals || [],
    recommended_products: creator.recommended_products || [],
    recommended_campaign_angle: creator.recommended_campaign_angle || "",
  };
}

function operationRecentPostsByCreator() {
  return Object.fromEntries(
    state.creators.map((creator) => [
      creator.creator_id,
      (state.recentPostsByCreator[creator.creator_id] || []).slice(0, 20).map(toRecentPostSnapshot),
    ])
  );
}

function ensureOperationScreenResults() {
  const results = {};
  state.creators.forEach((creator) => {
    const existing = state.recentScreenResults[creator.creator_id];
    if (existing) {
      results[creator.creator_id] = existing;
      return;
    }
    const posts = (state.recentPostsByCreator[creator.creator_id] || []).slice(0, 20);
    results[creator.creator_id] = posts.length
      ? previewRecentPostsScreen(creator, posts)
      : buildNoPostsScreenResult();
    state.recentScreenResults[creator.creator_id] = results[creator.creator_id];
  });
  return results;
}

function localEnrichmentFromCreator(creator) {
  return {
    creator_id: creator.creator_id,
    username: creator.username,
    display_name: creator.display_name || creator.username,
    primary_country: creator.country,
    country_confidence: 0.85,
    language: creator.language || "es",
    platforms: [creator.platform || "tiktok"],
    contact_channels: [creator.platform || "profile"],
    normalized_categories: creator.recommended_products || [],
    commerce_readiness: creator.avg_views >= 10000 ? "audience_ready" : "needs_validation",
    duplicate_key: `${creator.platform || "tiktok"}:${creator.username}`,
    missing_data: creator.profile_url ? [] : ["profile_url"],
    enrichment_status: creator.profile_url ? "ready" : "needs_review",
    next_action: "run_recent_20_screen",
  };
}

function localRecentApply(creators, screenResults) {
  const items = creators.map((creator) => {
    const result = screenResults[creator.creator_id] || buildNoPostsScreenResult();
    const decision = result.suitability_decision || "human_review";
    const queue =
      decision === "pass_to_full_analysis"
        ? "full_analysis_queue"
        : decision === "avoid"
          ? "avoid_queue"
          : decision === "recheck_later"
            ? "recheck_later_queue"
            : "human_review_queue";
    return {
      creator_id: creator.creator_id,
      username: creator.username,
      suitability_decision: decision,
      suitability_score: result.suitability_score || 0,
      queue,
      next_action: queue === "full_analysis_queue" ? "run_profile_comment_multimodal_analysis" : "operator_review",
      matched_product_categories: result.matched_product_categories || [],
      coverage_gaps: result.coverage_gaps || [],
      risk_notes: result.risk_notes || [],
      post_count_analyzed: result.post_count_analyzed || 0,
    };
  });
  return {
    status: "applied",
    persistence_status: "local_preview",
    items,
    queue_counts: countBy(items, "queue"),
  };
}

function localCampaignMatch(creators, screenResults, productCategory, country) {
  const items = creators
    .filter((creator) => creator.country === country)
    .map((creator) => {
      const screen = screenResults[creator.creator_id] || {};
      const productMatch =
        (creator.recommended_products || []).includes(productCategory) ||
        (screen.matched_product_categories || []).includes(productCategory);
      const matchScore = Math.max(
        0,
        Math.min(
          100,
          Math.round(
            Number(creator.final_score || 0) * 0.55 +
              Number(screen.suitability_score || 0) * 0.25 +
              (productMatch ? 12 : -6) -
              Number(creator.risk_penalty || 0) * 0.8
          )
        )
      );
      return {
        ...creator,
        campaign_product_category: productCategory,
        product_match: productMatch,
        recent_posts_decision: screen.suitability_decision,
        recent_posts_score: screen.suitability_score || 0,
        match_score: matchScore,
        priority_label: matchScore >= 85 && Number(creator.risk_penalty || 0) <= 5 ? "priority_outreach" : "outreach_candidate",
        match_reasons: productMatch ? [`matched_product:${productCategory}`, "recent_20_signal"] : ["minimum_filter_match"],
      };
    })
    .filter((item) => item.match_score >= 70)
    .sort((left, right) => right.match_score - left.match_score)
    .map((item, index) => ({ ...item, rank: index + 1 }));
  return {
    status: "matched",
    items,
    summary: {
      matched_count: items.length,
      priority_outreach: items.filter((item) => item.priority_label === "priority_outreach").length,
      human_review: items.filter((item) => item.priority_label === "human_review").length,
    },
  };
}

function localOutreachPlan(matchedItems, productCategory) {
  const items = matchedItems.map((candidate) => ({
    creator_id: candidate.creator_id,
    username: candidate.username,
    rank: candidate.rank,
    priority_label: candidate.priority_label,
    dm_variant: "product_review",
    dm_message: `Hola ${candidate.display_name || candidate.username}, equipo Briwell. Tu contenido de skincare encaja con una colaboracion K-Beauty para ${formatProductCategory(productCategory)}.`,
    offer_terms: {
      fee_usd: candidate.follower_count >= 50000 ? 220 : 140,
      sample_product: true,
      deliverables: ["1 short-form video", "story/link placement if available"],
      usage_rights_days: 30,
      tracking: { coupon_code_required: true, tracking_url_required: true },
    },
    claims_check_status: "needs_review",
    crm_status: "dm_drafted",
    manual_send_required: true,
    next_action: "run_claims_check_then_operator_approval",
  }));
  return {
    status: "planned",
    persistence_status: "local_preview",
    items,
    send_policy: {
      auto_send_enabled: false,
      required_before_send: ["claims_check_passed", "human_approval", "manual_send_confirmed"],
    },
  };
}

function localCrmBoard(outreachItems) {
  return {
    status: "ok",
    persistence_status: "local_preview",
    board: {
      total: outreachItems.length,
      counts: countBy(outreachItems, "crm_status"),
      stages: ["dm_drafted", "approved", "dm_sent", "replied", "accepted"].map((status) => ({
        status,
        count: outreachItems.filter((item) => item.crm_status === status).length,
        items: outreachItems.filter((item) => item.crm_status === status),
      })),
      next_actions: outreachItems.length
        ? ["Run claims check and human approval for drafted DMs."]
        : ["Prepare outreach drafts for matched candidates."],
      manual_send_policy: {
        auto_send_enabled: false,
        required_before_send: ["claims_check_passed", "human_approval", "manual_send_confirmed"],
      },
    },
  };
}

function buildOperationPerformanceSnapshots(matchedItems) {
  const fallbackViews = Number(byId("snapshotViews")?.value || 0);
  // snapshotRevenue is entered in the selected recording currency; convert to
  // USD with the recorded FX rate so rollup previews stay in one unit.
  const revenueTriple = readSnapshotRevenueTriple();
  const fallbackRevenue = revenueTriple.fxRate > 0
    ? Math.round(revenueTriple.amount * revenueTriple.fxRate * 100) / 100
    : 0;
  return (matchedItems.length ? matchedItems : state.creators.slice(0, 1)).map((item, index) => ({
    campaign_id: "campaign-1",
    creator_id: item.creator_id,
    post_url: byId("snapshotPostUrl")?.value || `https://www.tiktok.com/@${item.username || "creator"}/video/${index + 1}`,
    tracking_url: `https://go.briwell.co/track/${item.creator_id}`,
    coupon_code: byId("snapshotCoupon")?.value || `BRI-${item.country || "MX"}-${index + 1}`,
    view_count: fallbackViews || item.avg_views || 0,
    like_count: Math.round((fallbackViews || item.avg_views || 0) * 0.06),
    comment_count: Math.round((fallbackViews || item.avg_views || 0) * 0.005),
    share_count: Math.round((fallbackViews || item.avg_views || 0) * 0.002),
    click_count: Math.round((fallbackViews || item.avg_views || 0) * 0.018),
    conversion_count: Math.round((fallbackViews || item.avg_views || 0) * 0.001),
    revenue_usd: fallbackRevenue || Math.round((item.match_score || item.final_score || 0) * 4),
  }));
}

function localPerformanceRollup(matchedItems) {
  const snapshots = buildOperationPerformanceSnapshots(matchedItems);
  const spend = Number(byId("campaignBudget")?.value || 0);
  const summary = {
    snapshot_count: snapshots.length,
    view_count: snapshots.reduce((sum, item) => sum + item.view_count, 0),
    like_count: snapshots.reduce((sum, item) => sum + item.like_count, 0),
    comment_count: snapshots.reduce((sum, item) => sum + item.comment_count, 0),
    share_count: snapshots.reduce((sum, item) => sum + item.share_count, 0),
    click_count: snapshots.reduce((sum, item) => sum + item.click_count, 0),
    conversion_count: snapshots.reduce((sum, item) => sum + item.conversion_count, 0),
    revenue_usd: snapshots.reduce((sum, item) => sum + item.revenue_usd, 0),
  };
  summary.engagement_count = summary.like_count + summary.comment_count + summary.share_count;
  summary.roas = spend ? Number((summary.revenue_usd / spend).toFixed(2)) : null;
  return {
    status: "ok",
    rollup: {
      summary,
      creator_leaderboard: snapshots
        .map((item) => ({
          creator_id: item.creator_id,
          view_count: item.view_count,
          conversion_count: item.conversion_count,
          revenue_usd: item.revenue_usd,
        }))
        .sort((left, right) => right.revenue_usd - left.revenue_usd),
      next_actions: ["Use creator leaderboard to expand budget toward top performers."],
    },
  };
}

function renderScreenCompact(result) {
  return `
    <div class="screen-compact">
      <div class="screen-compact-head">
        <span class="decision-pill ${decisionClass(result.suitability_decision)}">${escapeHtml(decisionLabel(result.suitability_decision))}</span>
        <strong>${escapeHtml(String(Math.round(Number(result.suitability_score || 0))))}</strong>
      </div>
      <div class="policy-line"><span>제품</span><strong>${escapeHtml(formatProductList(result.matched_product_categories).join(", ") || "데이터 필요")}</strong></div>
      <div class="policy-line"><span>부족 데이터</span><strong>${escapeHtml((result.coverage_gaps || result.missing_data || []).slice(0, 2).join(", ") || "없음")}</strong></div>
    </div>
  `;
}

function renderScreenPlaceholder(creatorId) {
  const count = (state.recentPostsByCreator[creatorId] || []).length;
  return `
    <div class="screen-compact">
      <div class="screen-compact-head">
        <span class="decision-pill decision-review">미스크리닝</span>
        <strong>${escapeHtml(String(count))}/20</strong>
      </div>
      <div class="policy-line"><span>다음</span><strong>최근 20개 스크리닝 실행</strong></div>
    </div>
  `;
}

function renderScreenFull(result, creator, postCount) {
  const gaps = result.coverage_gaps || result.missing_data || [];
  return `
    <div class="screening-grid">
      <article class="screening-card score-card">
        <span>적합성 점수</span>
        <strong>${escapeHtml(String(Math.round(Number(result.suitability_score || 0))))}</strong>
        <small>${creator ? `@${escapeHtml(creator.username)}` : "후보"} · 게시물 ${escapeHtml(postCount)} / 20</small>
      </article>
      <article class="screening-card">
        <span>판정</span>
        <strong><span class="decision-pill ${decisionClass(result.suitability_decision)}">${escapeHtml(decisionLabel(result.suitability_decision))}</span></strong>
        <small>${escapeHtml(result.next_step || "operator_review")}</small>
      </article>
      <article class="screening-card">
        <span>제품 매칭</span>
        <strong>${escapeHtml(formatProductList(result.matched_product_categories).join(", ") || "데이터 필요")}</strong>
        <small>K-Beauty 신호 ${escapeHtml(formatPercent(Number(result.kbeauty_signal_ratio || 0) * 100))}</small>
      </article>
      <article class="screening-card">
        <span>부족 데이터</span>
        <strong>${escapeHtml(String(gaps.length))}</strong>
        <small>${escapeHtml(gaps.slice(0, 3).join(", ") || "없음")}</small>
      </article>
    </div>
    <div class="screening-notes">
      <div>
        <h3>리스크 메모</h3>
        <p>${escapeHtml((result.risk_notes || []).join(", ") || "사전 리스크 메모 없음")}</p>
      </div>
      <div>
        <h3>다음 액션</h3>
        <p>${escapeHtml(formatNextStep(result.next_step))}</p>
      </div>
      <div>
        <h3>관찰</h3>
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
  return parseCsvWithMeta(text).rows;
}

function parseCsvWithMeta(text) {
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
  if (!cleanRows.length) return { headers: [], rows: [] };
  const headers = cleanRows[0].map((header) => normalizeHeader(header));
  return {
    headers,
    rows: cleanRows.slice(1).map((items) => {
      const object = {};
      headers.forEach((header, index) => {
        object[header] = String(items[index] || "").trim();
      });
      return object;
    }),
  };
}

function parseManualPosts(text) {
  return parseManualPostsWithMeta(text).rows;
}

function parseManualPostsWithMeta(text) {
  if (!text) return { headers: [], rows: [] };
  const firstLine = text.split(/\r?\n/)[0].toLowerCase();
  if (firstLine.includes("url") || firstLine.includes("caption") || firstLine.includes("view_count")) {
    return parseCsvWithMeta(text);
  }
  const rowHeaders = ["url", "caption", "hashtags", "view_count", "like_count", "comment_count"];
  const derivedHeaders = ["creator_id", ...rowHeaders, "source_type", "source_risk_level"];
  return {
    headers: derivedHeaders,
    rows: text
      .split(/\r?\n/)
      .filter((line) => line.trim())
      .map((line) => {
        const values = parseCsv(`${rowHeaders.join(",")}\n${line}`)[0] || {};
        return values;
      }),
  };
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
    url: `https://www.tiktok.com/@${creatorId}/video/${index + 1}`,
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
      <span>평균조회 ${escapeHtml(formatCompactNumber(creator.avg_views))}</span>
      <span>인게이지먼트 ${escapeHtml(formatPercent(creator.engagement_rate))}</span>
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
  if (normalized === "low") return '<span class="badge green">낮음</span>';
  if (normalized === "low_medium") return '<span class="badge amber">낮음/중간</span>';
  if (normalized === "medium") return '<span class="badge amber">중간</span>';
  return '<span class="badge red">차단</span>';
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
  if (levels.some((level) => !["low", "low_medium", "medium"].includes(level))) return "high";
  if (levels.includes("medium")) return "medium";
  if (levels.includes("low_medium")) return "low_medium";
  return "low";
}

function sourceTypeForImport(items) {
  const types = unique((items || []).map((item) => normalizeSourceType(item.source_type)).filter(Boolean));
  if (types.length === 1 && ALLOWED_IMPORT_SOURCE_TYPES.includes(types[0])) return types[0];
  return "manual";
}

function sourceRiskForCreator(creatorId) {
  const creator = state.creators.find((item) => item.creator_id === creatorId);
  return normalizeRisk(creator?.source_risk_level || "low");
}

function normalizeSourceType(value) {
  const normalized = String(value || "manual").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "api") return "official_api";
  if (normalized === "provider") return "approved_provider";
  if (normalized === "creator") return "creator_provided";
  return normalized;
}

function normalizeRisk(value) {
  const normalized = String(value || "low").trim().toLowerCase().replace("-", "_");
  if (["low", "low_medium", "medium"].includes(normalized)) return normalized;
  if (normalized === "low/medium") return "low_medium";
  return normalized || "low";
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
    review_creator: "리뷰 크리에이터",
    beauty_educator: "뷰티 에듀케이터",
    ugc_creator: "UGC 제작자",
    viral_micro: "바이럴 마이크로",
    commerce_creator: "커머스 크리에이터",
    brand_builder: "브랜드 빌더",
    avoid: "사용 안 함",
  };
  return labels[segment] || segment;
}

function formatSourceTypes(types) {
  const labels = {
    manual: "수동 임포트",
    official_api: "공식 API",
    approved_provider: "승인 Provider",
    creator_provided: "크리에이터 제공",
    provider_scrape: "Provider 스크래핑",
    browser_automation: "브라우저 자동화",
    captcha_bypass: "CAPTCHA 우회",
    public_page_scrape: "공개 페이지 스크래핑",
  };
  return (types || []).map((type) => labels[type] || type);
}

function formatMarket(country) {
  const labels = {
    MX: "멕시코",
    PE: "페루",
    EC: "에콰도르",
  };
  return labels[country] || country || "";
}

function formatProductCategory(category) {
  const labels = {
    sunscreen: "선스크린",
    calming_serum: "카밍 세럼",
    cleanser: "클렌저",
    sheet_mask: "시트 마스크",
    cushion_foundation: "쿠션 파운데이션",
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
  return value ? "활성" : "비활성";
}

function formatReadiness(status) {
  const labels = {
    ok: "준비",
    blocked: "차단",
    ready_with_warnings: "경고",
    unknown: "알 수 없음",
  };
  return labels[status] || status || "알 수 없음";
}

function formatPolicyText(policy) {
  if (!policy) return "후보 분석에는 승인된 수집 경로만 허용됩니다.";
  if (policy.includes("Unauthorized scraping")) {
    return "무단 스크래핑은 차단됩니다. 수동 임포트, 공식 API, 승인 Provider, 크리에이터 제공 데이터만 사용하세요.";
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
    discovery: "발굴",
    concern: "고민",
    format: "포맷",
    commerce: "커머스",
  };
  return labels[value] || value;
}

function decisionLabel(decision) {
  const labels = {
    pass_to_full_analysis: "통과",
    pass: "통과",
    human_review: "수동 검수",
    recheck_later: "추후 재검토",
    avoid: "제외",
  };
  return labels[decision] || "수동 검수";
}

function decisionClass(decision) {
  if (decision === "pass_to_full_analysis" || decision === "pass") return "decision-pass";
  if (decision === "recheck_later") return "decision-recheck";
  if (decision === "avoid") return "decision-avoid";
  return "decision-review";
}

function formatNextStep(value) {
  const labels = {
    run_full_profile_comment_multimodal_analysis: "프로필·댓글·멀티모달 전체 분석 실행",
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
  updateDataStateIndicator(status, label);
}

function updateDataStateIndicator(status, label) {
  const pill = byId("dataStatePill");
  const pillLabel = byId("dataStateLabel");
  const banner = byId("dataStateBanner");
  const isLive = status === "online";
  if (pillLabel) {
    pillLabel.textContent = isLive ? "라이브 모드" : label;
  }
  if (pill) {
    pill.classList.remove("is-online", "is-offline", "is-live");
    if (isLive) pill.classList.add("is-live");
    if (status === "offline") pill.classList.add("is-offline");
  }
  if (banner) {
    banner.classList.toggle("active", true);
    banner.classList.toggle("is-live", isLive);
    banner.textContent = isLive
      ? "라이브 모드 · 쓰기 작업이 실제 서버에 기록됩니다"
      : "미리보기 모드 · 목업 데이터 (정산 반영 안 됨)";
  }
  updateWriteActionChips(isLive);
}

function updateWriteActionChips(isLive) {
  document.querySelectorAll("[data-write-action]").forEach((button) => {
    button.setAttribute("data-write-mode", isLive ? "live" : "preview");
    button.setAttribute("data-write-mode-label", isLive ? "LIVE" : "PREVIEW");
  });
}

function isWriteConfirmSuppressed() {
  try {
    const until = Number(sessionStorage.getItem(WRITE_CONFIRM_SUPPRESS_KEY) || 0);
    return until > Date.now();
  } catch (_error) {
    // Storage access can throw in strict-private/blocked-storage contexts.
    // Fail to "not suppressed" so the write still goes through the confirm
    // modal instead of silently downgrading to a fake local preview.
    return false;
  }
}

function suppressWriteConfirmFor(ms) {
  try {
    sessionStorage.setItem(WRITE_CONFIRM_SUPPRESS_KEY, String(Date.now() + ms));
  } catch (_error) {
    // Best-effort only; if storage is unavailable the "don't ask again"
    // checkbox simply won't persist across writes, which is safe.
  }
}

function isAllowlistedWriteEndpoint(path) {
  return WRITE_CONFIRM_ALLOWLIST.some((endpoint) => path.startsWith(endpoint));
}

async function writeGate({ path, method, apiBase }) {
  // Fail-closed: until the first health check resolves, connectivity is
  // unknown. Treat unknown the same as live (require confirmation) instead
  // of assuming preview, so an already-live backend can never receive an
  // unconfirmed write during the initial load race.
  if (!state.apiConnectivityChecked) return openWriteConfirmModal({ path, method, apiBase });
  if (!state.apiOnline) return true;
  if (isAllowlistedWriteEndpoint(path)) return true;
  // The operations pipeline asks for a single up-front confirmation covering
  // all of its sequential writes (see confirmOperationsPipelineWrite) instead
  // of prompting once per step. Only honor the token for calls made while a
  // pipeline run is actually in flight and already approved.
  if (pipelineWriteApprovalActive) return true;
  if (isWriteConfirmSuppressed()) return true;
  return openWriteConfirmModal({ path, method, apiBase });
}

function openWriteConfirmModal({ path, method, apiBase }) {
  return new Promise((resolve) => {
    const modal = byId("writeConfirmModal");
    const scrim = byId("writeConfirmScrim");
    if (!modal || !scrim) {
      resolve(true);
      return;
    }
    byId("writeConfirmMethod").textContent = method;
    byId("writeConfirmEndpoint").textContent = path;
    byId("writeConfirmApiBase").textContent = apiBase;
    const suppressCheckbox = byId("writeConfirmSuppressCheckbox");
    if (suppressCheckbox) suppressCheckbox.checked = false;

    const previouslyFocused = document.activeElement;

    const cleanup = (result) => {
      modal.classList.remove("active");
      scrim.classList.remove("active");
      modal.setAttribute("aria-hidden", "true");
      document.removeEventListener("keydown", onKeydown, true);
      byId("writeConfirmProceedButton").removeEventListener("click", onProceed);
      byId("writeConfirmCancelButton").removeEventListener("click", onCancel);
      scrim.removeEventListener("click", onCancel);
      if (previouslyFocused && typeof previouslyFocused.focus === "function") {
        previouslyFocused.focus();
      }
      resolve(result);
    };

    const onProceed = () => {
      if (suppressCheckbox && suppressCheckbox.checked) {
        suppressWriteConfirmFor(WRITE_CONFIRM_SUPPRESS_MS);
      }
      cleanup(true);
    };
    const onCancel = () => cleanup(false);
    const onKeydown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key === "Tab") {
        trapFocus(event, modal);
      }
    };

    byId("writeConfirmProceedButton").addEventListener("click", onProceed);
    byId("writeConfirmCancelButton").addEventListener("click", onCancel);
    scrim.addEventListener("click", onCancel);
    document.addEventListener("keydown", onKeydown, true);

    modal.classList.add("active");
    scrim.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    window.requestAnimationFrame(() => modal.focus());
  });
}

function trapFocus(event, container) {
  const focusable = container.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function bindWriteConfirmModal() {
  const modal = byId("writeConfirmModal");
  if (!modal) return;
  // Initialize write-action chips to the preview state before the first
  // health check resolves; refreshFromApi/setApiStatus will update this
  // once connectivity is known. Per-open dialog wiring lives in
  // openWriteConfirmModal, which attaches and tears down its own listeners.
  updateWriteActionChips(false);
}

const RESULT_CHIP_RULES = [
  { test: (status) => status === "persisted", tone: "success", text: "✓ 실제 서버 DB에 기록됨" },
  {
    test: (status) => status === "validated_not_persisted",
    tone: "warn",
    text: "⚠ 검증만 됨 · DB 비활성이라 저장 안 됨",
  },
  { test: (status) => status === "cancelled_by_user", tone: "neutral", text: "취소됨 · 아무것도 기록되지 않음" },
  {
    test: (status) => /preview/i.test(status || ""),
    tone: "neutral",
    text: "미리보기 · 서버에 반영 안 됨",
  },
];

function resolveResultChip(payload) {
  const status = payload && typeof payload === "object" ? payload.status : undefined;
  if (!status) return null;
  const rule = RESULT_CHIP_RULES.find((candidate) => candidate.test(status));
  return rule ? { tone: rule.tone, text: rule.text } : null;
}

function showResult(id, payload) {
  const box = byId(id);
  box.classList.add("active");
  box.innerHTML = "";

  const chip = resolveResultChip(payload);
  if (chip) {
    const chipEl = document.createElement("span");
    chipEl.className = `result-chip result-chip-${chip.tone}`;
    chipEl.textContent = chip.text;
    box.appendChild(chipEl);
  }

  const body = document.createElement("pre");
  body.className = "result-body";
  body.textContent = JSON.stringify(payload, null, 2);
  box.appendChild(body);
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
