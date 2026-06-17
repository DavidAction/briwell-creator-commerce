const state = {
  apiOnline: false,
  activeCountry: "ALL",
  selectedCreatorId: "creator-1",
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
        "데일리 선케어 루틴, 솔직 리뷰, 구매 링크 전환 설계에 적합한 프리미엄 리뷰형 후보",
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
        "성분 설명과 민감성 피부 루틴 강점 기반 교육형 K-뷰티 캠페인 적합 후보",
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
        "루틴 시연형 콘텐츠 제작 가능성, UGC 확보 및 제품 사용감 검증 적합 후보",
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
      detail: "안티에이징 표현, 국가별 화장품 광고 기준 추가 검토 필요",
    },
    {
      creator: "rutina.ec",
      creator_id: "creator-3",
      status: "Contact Check",
      badge: "blue",
      detail: "외부 플랫폼 발송 전 수동 연락 경로 및 Do-Not-Contact 상태 확인 필요",
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
    byId("metricHealth").textContent = health?.status === "ok" ? "Online" : health?.status || "Online";
    byId("metricHealthNote").textContent = "Connected to live API";
    byId("metricReadiness").textContent = formatReadiness(readiness?.status);
    renderSourcePolicy(sourcePolicy);
    renderAiProvider(aiProvider);

    if (Array.isArray(creators?.items) && creators.items.length > 0) {
      state.creators = creators.items.map(normalizeApiCreator);
    }
  } catch (_error) {
    state.apiOnline = false;
    setApiStatus("offline", "Mock Mode");
    byId("metricHealth").textContent = "Mock";
    byId("metricHealthNote").textContent = "Local dashboard fallback";
    byId("metricReadiness").textContent = "Local";
    renderSourcePolicy(null);
    renderAiProvider(null);
  }
  renderAll();
}

function renderAll() {
  byId("metricCandidates").textContent = String(filteredCreators().length);
  byId("metricQueue").textContent = String(state.reviewItems.length);
  renderTalentRadar();
  renderPriorityTable();
  renderReviewQueue();
  renderCandidateTable();
  renderPayoutTable();
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
    <p>${escapeHtml(creator.recommended_campaign_angle || "협업 전 최종 검토 필요")}</p>
    <button class="button primary" data-add-to-campaign="${escapeHtml(creator.creator_id)}">Shortlist Talent</button>
  `;
  bindShortlistButtons();
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
    });
    renderDiscoveryRows(payload.items || fallback);
  } catch (_error) {
    renderDiscoveryRows(fallback);
  }
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
    candidate_snapshots: selected.map((creator) => ({
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
    })),
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

function normalizeApiCreator(creator) {
  return {
    creator_id: creator.creator_id || creator.id || creator.username,
    username: creator.username || "creator",
    display_name: creator.display_name || creator.username || "Creator",
    country: creator.country || "MX",
    profile_url: creator.profile_url || "",
    profile_image_url: creator.profile_image_url || creator.avatar_url || creator.thumbnail_url || fallbackProfileImage(creator),
    channel_image_url: creator.channel_image_url || creator.cover_image_url || fallbackChannelImage(creator),
    follower_count: creator.follower_count || 0,
    avg_views: creator.avg_views || creator.average_views || 0,
    engagement_rate: creator.engagement_rate || 0,
    platform: creator.platform || "tiktok",
    source_risk_level: creator.source_risk_level || "low",
    final_score: creator.final_score || creator.score || 70,
    risk_penalty: creator.risk_penalty || 5,
    segment: creator.segment || "review_creator",
    signals: creator.signals || creator.recommended_products || ["Profile"],
    recommended_products: creator.recommended_products || [],
    recommended_campaign_angle: creator.recommended_campaign_angle || "",
  };
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
  if (state.activeCountry === "ALL") {
    return state.creators;
  }
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
    .slice(0, 4)
    .map((signal) => `<span class="badge teal">${escapeHtml(signal)}</span>`)
    .join(" ");
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
  if (!policy) {
    return "Only compliant acquisition paths are allowed for candidate analysis.";
  }
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

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
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
