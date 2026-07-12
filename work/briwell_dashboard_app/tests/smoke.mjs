import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const files = {
  html: readFileSync(join(root, "index.html"), "utf8"),
  css: readFileSync(join(root, "styles.css"), "utf8"),
  client: readFileSync(join(root, "api-client.js"), "utf8"),
  app: readFileSync(join(root, "app.js"), "utf8"),
  vercel: readFileSync(join(root, "vercel.json"), "utf8"),
  creatorTemplate: readFileSync(join(root, "templates", "creator_candidates_template.csv"), "utf8"),
  postsTemplate: readFileSync(join(root, "templates", "recent_posts_20_template.csv"), "utf8"),
};

const requiredViews = [
  "view-command",
  "view-discovery",
  "view-intake",
  "view-candidates",
  "view-campaign",
  "view-review",
  "view-tracking",
  "view-settlement",
  "view-partners",
];

const requiredEndpoints = [
  "/health",
  "/ops/readiness",
  "/discovery/source-policy",
  "/ai/provider-status",
  "/providers/tiktok/status",
  "/providers/tiktok/keyword-playbook",
  "/providers/tiktok/discovery-runs",
  "/discovery/plans",
  "/creators/import",
  "/videos/import",
  "/analysis-jobs/run-recent-posts-screen",
  "/operations/import-quality-logs",
  "/operations/creator-enrichment",
  "/operations/recent-posts/apply",
  "/operations/campaign-match",
  "/operations/outreach-plan",
  "/operations/outreach-crm/board",
  "/operations/performance-rollup",
  "/operations/acquisition-orchestration",
  "/campaigns",
  "/outreach/claims-check",
  "/outreach/status-transition",
  "/performance/snapshots",
  "/settlements/contracts",
  "/commerce/discount-codes/issue",
  "/providers/creator-provided/import",
  "/portal/tokens",
  "/partners",
  "/partners/review-queue",
];

// --- Phase 3 elevation: currency-explicit revenue + Shopify discount issuance ---
assert(files.html.includes("snapshotCurrency"), "snapshot currency selector missing");
assert(files.html.includes("snapshotFxRate"), "snapshot FX rate input missing");
assert(files.app.includes("revenue_amount") && files.app.includes("revenue_currency") && files.app.includes("fx_rate_usd"), "snapshot must send the currency-explicit revenue triple");
assert(files.app.includes("updateSnapshotFxAvailability"), "USD FX lock control missing");
assert(files.html.includes("Shopify 할인코드 발급"), "Shopify discount issuance panel missing");
assert(files.html.includes('id="issueDiscountCodeButton" data-write-action'), "discount issuance button must carry the write-action badge");
assert(files.app.includes("issueDiscountCode"), "discount issuance handler missing");
assert(files.client.includes("issueDiscountCode"), "discount issuance API client method missing");
assert(files.html.includes("Shopify 자사몰 (주력)"), "campaign channel must lead with Shopify per 0.0.1 strategy");
["view-discovery", "view-candidates", "view-tracking"].forEach((view) => {
  const viewIndex = files.html.indexOf(`id="${view}"`);
  const nextChunk = files.html.slice(viewIndex, viewIndex + 200);
  assert(nextChunk.includes("content-grid"), `${view} must use the elevated content-grid layout`);
});

// --- Phase 3 remainder: per-screen KPI metric strips (candidates/tracking/settlement) ---
[
  ["view-candidates", "candidatesKpis"],
  ["view-tracking", "trackingKpis"],
  ["view-settlement", "settlementKpis"],
].forEach(([view, mount]) => {
  const viewIndex = files.html.indexOf(`id="${view}"`);
  const nextChunk = files.html.slice(viewIndex, viewIndex + 200);
  assert(nextChunk.includes(`id="${mount}"`), `${view} must open with its KPI strip mount (${mount})`);
});
assert(files.app.includes("buildCandidateKpis"), "candidates KPI builder missing");
assert(files.app.includes("buildTrackingKpis"), "tracking KPI builder missing");
assert(files.app.includes("buildSettlementKpis"), "settlement KPI builder missing");
assert(files.app.includes("renderScreenKpis"), "per-screen KPI renderer missing");
assert(files.css.includes(".screen-kpis"), "per-screen KPI strip styling missing");
// KPI strips must aggregate real recorded writes, not hardcoded numbers: session
// write logs exist and every recorder re-renders the strips.
assert(files.app.includes("sessionSnapshots"), "session snapshot log missing");
assert(files.app.includes("sessionContracts"), "session contract log missing");
assert(files.app.includes("sessionDiscountCodes"), "session discount code log missing");
["recordSessionSnapshot", "recordSessionContract", "recordSessionDiscountCode"].forEach((fn) => {
  assert(files.app.includes(`function ${fn}(`), `${fn} session recorder missing`);
});
// Payout table and settlement KPIs must share one data source so they cannot disagree.
assert(files.app.includes("PAYOUT_ROWS"), "shared payout rows source missing");
// API-rejected writes (error.payload present) must never count as recorded work.
assert(
  /if\s*\(!error\.payload\)\s*recordSessionSnapshot/.test(files.app) &&
    /if\s*\(!error\.payload\)\s*recordSessionContract/.test(files.app) &&
    /if\s*\(!error\.payload\)\s*recordSessionDiscountCode/.test(files.app),
  "session recorders must only fire on the offline preview fallback, not on API rejections"
);

// --- Derived-figure honesty markers: estimates must never read as measured data ---
assert(files.css.includes(".derived-tag"), "derived tag styling missing");
assert(files.css.includes(".derived-note"), "derived note styling missing");
assert(files.html.includes("파이프라인 GMV 예측 <i class=\"derived-tag\""), "GMV forecast metric must carry the 추정 tag");
assert(files.html.includes('id="campaignFunnelNote"'), "campaign funnel derived-note mount missing");
assert(files.html.includes("추정 곡선 · 실측 매출 이력 축적 전 대표 형상"), "GMV trend hero derived disclaimer missing");
assert(files.html.includes("현재 값 기반 대표 형상입니다"), "sparkline derived footnote missing");
assert(/derived:\s*!brandSafe/.test(files.app), "brand-safe funnel stage must flag ratio-derived counts");
assert(files.app.includes('stage.derived ? \'<i class="derived-tag"'), "funnel renderer must tag derived stages");
assert(files.app.includes("추정 전기 대비"), "GMV hero delta badge must be labeled as an estimate");

// --- creator_provided submission channel (slimmed-C step (a); docs/CREATOR_DATA_REQUEST_ES.md) ---
files.cpProfileTemplate = readFileSync(join(root, "templates", "creator_provided_profile_template.csv"), "utf8");
files.cpPostsTemplate = readFileSync(join(root, "templates", "creator_provided_posts_template.csv"), "utf8");
assert(files.html.includes("크리에이터 제공 데이터 (creator_provided)"), "creator_provided intake panel missing");
assert(files.html.includes('id="cpProfileCsvInput"'), "creator_provided profile CSV input missing");
assert(files.html.includes('id="cpPostsCsvInput"'), "creator_provided posts CSV input missing");
assert(files.html.includes('id="runCreatorProvidedButton" data-compute-action'), "normalize button must carry the compute-action badge (no DB write)");
assert(files.html.includes('id="creatorRequestText"'), "Spanish request copy textarea missing");
assert(files.app.includes("parseCreatorProvidedFiles"), "creator_provided CSV parser missing");
assert(files.app.includes("runCreatorProvidedImport"), "creator_provided normalize runner missing");
assert(files.app.includes("applyCreatorProvidedToIntake"), "creator_provided intake application missing");
assert(files.app.includes("buildLocalCreatorProvidedRun"), "creator_provided offline preview fallback missing");
assert(files.client.includes("importCreatorProvided"), "creator_provided API client method missing");
// Consent is fail-closed: rows without consent_ref/provided_at must block normalization.
assert(files.app.includes("consent_blocked"), "consent-missing rows must block normalization");
assert(/if\s*\(parsed\.issues\.length\)\s*{[\s\S]{0,400}?return;/.test(files.app), "runCreatorProvidedImport must refuse to run with consent blockers");
// The normalize endpoint is pure compute, so it belongs on the write-confirm allowlist.
assert(/WRITE_CONFIRM_ALLOWLIST = \[[\s\S]*?"\/providers\/creator-provided\/import"/.test(files.app), "creator-provided import must be allowlisted as pure compute");
// Templates must carry the consent columns the operator fills before upload.
assert(files.cpProfileTemplate.includes("consent_ref") && files.cpProfileTemplate.includes("provided_at"), "profile template missing consent columns");
assert(files.cpPostsTemplate.includes("consent_ref") && files.cpPostsTemplate.includes("provided_at"), "posts template missing consent columns");

// --- Market news signals panel (slimmed-C step (b): public Google News RSS) ---
assert(files.html.includes("시장 뉴스 신호 (공개 RSS)"), "news signal panel missing from discovery view");
assert(files.html.includes('id="loadNewsSignalsButton"'), "news signal load button missing");
assert(files.html.includes('id="newsSignalsList"'), "news signal list mount missing");
assert(files.html.includes("크리에이터 데이터 아님"), "news panel must state items are market signals, not creator data");
assert(files.app.includes("loadNewsSignals"), "news signal loader missing");
assert(files.app.includes("renderNewsSignals"), "news signal renderer missing");
assert(files.app.includes("buildLocalNewsSignals"), "news signal offline fallback missing");
assert(files.app.includes("드라이런 샘플"), "dry-run news signals must be labeled as samples");
assert(files.client.includes("fetchNewsSignals"), "news signal API client method missing");
assert(files.css.includes(".news-signal-item"), "news signal styling missing");
// External headlines open in a new tab without opener access, and hostile feed
// URLs (javascript:/data:) must never become clickable hrefs.
assert(/news-signal-item[\s\S]{0,200}?rel="noopener noreferrer"/.test(files.app), "news links must use rel=noopener");
assert(files.app.includes("function safeExternalUrl("), "external URL scheme guard missing");
assert(files.app.includes("safeExternalUrl(item.url)"), "news link hrefs must pass through the scheme guard");

// --- Creator portal link issuance from the dashboard (briefing 0.0.17 deploy note) ---
assert(files.html.includes("크리에이터 포털 링크"), "portal link panel missing from settlement view");
assert(files.html.includes('id="issuePortalTokenButton" data-write-action'), "portal issue button must carry the write-action badge");
assert(files.html.includes('id="revokePortalTokenButton" data-write-action'), "portal revoke button must carry the write-action badge");
assert(files.html.includes('id="portalCreatorId"'), "portal creator id input missing");
assert(files.html.includes('id="portalPageBase"'), "portal page base input missing");
assert(files.client.includes("issuePortalToken"), "portal token issue API client method missing");
assert(files.client.includes("revokePortalTokens"), "portal token revoke API client method missing");
assert(files.app.includes("async function issuePortalToken"), "portal issue handler missing");
assert(files.app.includes("async function revokePortalTokens"), "portal revoke handler missing");
assert(files.app.includes("appendPortalLinkRow"), "portal link row renderer missing");
assert(files.css.includes(".portal-link-row"), "portal link row styling missing");
// Rotation semantics must be visible to the operator: issuing again kills the old link.
assert(files.html.includes("재발급하면 이전 링크는 즉시 무효"), "rotation kill-switch copy missing");
// Honesty gates: a token that only exists locally is a dead link, so the panel
// must fail loudly instead of fabricating an offline preview token, and a
// DB-off (validated_not_persisted) token must be flagged as non-working.
assert(files.app.includes('"api_unreachable"'), "portal handlers must fail honestly when the API is unreachable");
assert(files.app.includes("실제 포털 링크로 동작하지 않습니다"), "DB-off portal token must be flagged as non-working");
// The personal link embeds the token via the ?t= param the portal page reads
// (work/briwell_portal_app reads qs.get("t") || qs.get("token")).
assert(
  files.app.includes('${base.includes("?") ? "&" : "?"}t=${encodeURIComponent(token)}'),
  "portal link must embed the token as the t query param"
);

// --- Brand Partner Hub operator view (briefing 0.0.20) ---
assert(files.html.includes("파트너 허브"), "partner hub nav item missing");
assert(files.html.includes("브랜드 파트너 등록"), "partner registration panel missing");
assert(files.html.includes("허브 링크 발급"), "hub link issuance panel missing");
assert(files.html.includes("제품 초안 검수 큐"), "partner review queue panel missing");
assert(files.html.includes('id="createPartnerButton" data-write-action'), "create-partner button must carry the write-action badge");
assert(files.html.includes('id="issueHubTokenButton" data-write-action'), "hub token issue button must carry the write-action badge");
assert(files.html.includes('id="revokeHubTokenButton" data-write-action'), "hub token revoke button must carry the write-action badge");
assert(files.html.includes('id="approveDraftButton" data-write-action'), "approve button must carry the write-action badge");
assert(files.html.includes('id="rejectDraftButton" data-write-action'), "reject button must carry the write-action badge");
assert(!files.html.includes('id="loadReviewQueueButton" data-write-action'), "review-queue load is a read and must not carry the write badge");
assert(files.html.includes('id="reviewQueueTable"'), "review queue table mount missing");
["createPartner", "issueHubToken", "revokeHubTokens", "fetchPartnerReviewQueue", "reviewPartnerDraft"].forEach((method) => {
  assert(files.client.includes(method), `${method} API client method missing`);
});
["async function createPartner", "async function loadPartnerReviewQueue", "async function reviewPartnerDraft", "function renderPartnerReviewQueue"].forEach((fn) => {
  assert(files.app.includes(fn), `${fn} missing`);
});
// The human gate is explicit in the operator UI, and regulatory signals are
// labeled as non-legal-advice reference information.
assert(files.html.includes("인간 승인 게이트"), "human approval gate copy missing");
assert(files.html.includes("법률 자문 아님"), "not-legal-advice copy missing from review panel");
// Partner-supplied strings (company/product names) must render escaped.
assert(files.app.includes("escapeHtml(item.company_name"), "review queue must escape partner company names");
assert(files.app.includes("escapeHtml(draft.product_name"), "review queue must escape partner product names");
// Same token honesty rules as the creator portal panel.
assert(files.app.includes("실제 허브 링크로 동작하지 않습니다"), "DB-off hub token must be flagged as non-working");

// --- OIDC bearer token wiring (production API auth; docs/DEPLOY_RENDER.md step 5) ---
assert(files.html.includes('id="bearerTokenInput"'), "bearer token input missing from settings drawer");
assert(files.app.includes("bearerTokenInput"), "settings save must include the bearer token");
assert(files.client.includes('localStorage.removeItem("briwell.bearerToken")'), "clearing the bearer token field must remove the stored token");

assert(files.html.includes("Briwell Creator Commerce Intelligence"), "missing global dashboard title");
assert(files.html.includes("글로벌 MCN 운영 콘솔"), "missing Korean executive positioning copy");
assert(files.html.includes("오늘 처리해야 할 최고 우선순위 액션"), "missing Korean operator action copy");
assert(files.html.includes("후보 업로드"), "missing Korean intake navigation copy");
assert(files.html.includes("경영 현황"), "missing executive navigation");
assert(files.html.includes("후보 인테이크"), "missing talent intake navigation");
assert(files.html.includes("후보 인텔리전스"), "missing talent intelligence navigation");
assert(files.html.includes("브랜드 세이프티"), "missing brand safety navigation");
assert(files.html.includes("자동 발송 금지"), "manual-send safety gate missing");
assert(files.html.includes("파이프라인 GMV 예측"), "missing commerce forecast metric");
assert(files.html.includes("최근 20개 커버리지"), "missing recent 20 coverage metric");
assert(files.html.includes("커머스 커맨드 보드"), "missing commerce command board");
assert(files.html.includes("운영자 다음 액션"), "missing operator action queue");
assert(files.html.includes("성장 운영 엔진"), "missing operations engine");
assert(files.html.includes("runOperationsPipelineButton"), "missing operations pipeline action");
assert(files.html.includes("핵심 크리에이터 포트폴리오"), "missing visual portfolio leaders");
assert(files.html.includes("creatorCsvInput"), "missing creator CSV upload input");
assert(files.html.includes("downloadCreatorTemplateButton"), "missing creator CSV template download");
assert(files.html.includes("postCsvInput"), "missing recent posts CSV upload input");
assert(files.html.includes("downloadPostTemplateButton"), "missing recent posts template download");
assert(files.html.includes("manualPostsInput"), "missing manual recent posts input");
assert(files.html.includes("recentScreenMode"), "missing recent screen AI mode selector");
assert(files.html.includes("recentScreenModeHint"), "missing recent screen live-readiness hint");
assert(files.html.includes("라이브 Gemini 분석"), "missing live Gemini screening option");
assert(files.html.includes("runRecentScreenButton"), "missing recent 20 posts screen action");
assert(files.html.includes("임포트 품질 게이트"), "missing import quality gate");
assert(files.html.includes("importQualityGate"), "missing import quality gate mount");
assert(files.html.includes("coverageAudit"), "missing coverage audit mount");
assert(files.html.includes("TikTok Provider 수집"), "missing TikTok provider acquisition panel");
assert(files.html.includes("runTiktokProviderButton"), "missing provider discovery action");
assert(files.html.includes("keywordPlaybookSummary"), "missing provider keyword summary");
assert(files.html.includes("https://www.tiktok.com/@luzskincare/video/0000000000000000001"), "sample post URL should look channel-native");
assert(files.html.includes("talentRadar"), "missing talent radar mount");
assert(files.html.includes("ops-strip"), "missing operations status strip");
assert(files.html.includes("metricPipelineGmv"), "missing pipeline GMV metric mount");
assert(files.html.includes("operatorActions"), "missing operator actions mount");
assert(files.html.includes("operationsPipelineSummary"), "missing operations pipeline summary mount");
assert(files.html.includes("toast"), "missing toast feedback mount");
assert(files.css.includes("Pretendard Variable"), "Pretendard Variable font missing");
assert(files.css.includes("--sidebar: #0b1220"), "global navy theme token missing");
assert(files.css.includes(".creator-cover"), "creator cover styling missing");
assert(files.css.includes(".profile-avatar"), "profile avatar styling missing");
assert(files.css.includes(".command-board"), "command board styling missing");
assert(files.css.includes(".operator-actions"), "operator action styling missing");
assert(files.css.includes(".operations-pipeline"), "operations pipeline styling missing");
assert(files.css.includes(".provider-grid"), "provider acquisition styling missing");
assert(files.css.includes(".quality-gate"), "import quality gate styling missing");
assert(files.css.includes(".quality-summary"), "quality summary styling missing");
assert(files.css.includes(".validation-report"), "upload validation report styling missing");
assert(files.css.includes(".field-hint"), "field hint styling missing");
assert(files.css.includes(".screening-grid"), "recent posts screening layout missing");
assert(files.css.includes(".decision-pass"), "screening decision styling missing");
assert(files.css.includes(".audit-card"), "coverage audit card styling missing");
assert(files.css.includes(".row-selected"), "selected row styling missing");
assert(files.css.includes(".toast.active"), "toast active styling missing");
assert(files.app.includes("profile_image_url"), "profile image field missing");
assert(files.app.includes("channel_image_url"), "channel image field missing");
assert(files.app.includes("selectedCreatorId"), "selected creator state missing");
assert(files.app.includes("renderCommandMetrics"), "command metric renderer missing");
assert(files.app.includes("renderCommerceCommand"), "commerce command renderer missing");
assert(files.app.includes("renderOperatorActions"), "operator actions renderer missing");
assert(files.app.includes("runOperationsPipeline"), "operations pipeline runner missing");
assert(files.app.includes("runAcquisitionOrchestration"), "operations pipeline should call acquisition orchestration");
assert(files.app.includes("runTiktokProviderDiscovery"), "TikTok provider discovery runner missing");
assert(files.app.includes("latam_kbeauty_20s_30s"), "K-beauty keyword strategy missing");
assert(files.app.includes("api_status"), "operations pipeline must expose live/local status");
assert(files.app.includes("summarizeApiError"), "operations pipeline fallback should preserve API error context");
assert(files.app.includes("saveImportQualityLog"), "import quality operations API missing");
assert(files.app.includes("matchCampaignCandidates"), "campaign match operations API missing");
assert(files.client.includes("runAcquisitionOrchestration"), "acquisition orchestration API missing");
assert(files.app.includes("evaluateImportQuality"), "import quality evaluator missing");
assert(files.app.includes("validateCreatorDataset"), "creator quality validation missing");
assert(files.app.includes("validateRecentPostDataset"), "recent post quality validation missing");
assert(files.app.includes("renderValidationReport"), "upload validation report renderer missing");
assert(files.app.includes("parseCsvWithMeta"), "CSV parser metadata report missing");
assert(files.app.includes("parseCsv"), "CSV parser missing");
assert(files.app.includes("runRecentScreenForCreator"), "recent posts screen workflow missing");
assert(files.app.includes("allow_live_provider_calls"), "live Gemini request flag missing");
assert(files.app.includes("updateRecentScreenModeAvailability"), "live Gemini mode availability control missing");
assert(files.app.includes("live_gemini_unavailable"), "live Gemini unavailable guard missing");
assert(files.app.includes("persist_result"), "recent screen persistence flag missing");
assert(files.app.includes("live_gemini_screened"), "live Gemini result status missing");
assert(files.app.includes("coverageAudit"), "coverage audit state missing");
assert(files.app.includes("후보 숏리스트"), "shortlist action missing");
assert(files.app.includes("최근 게시물 20개까지 추가 수집"), "missing Korean recent-post next step copy");
assert(files.creatorTemplate.includes("source_type,source_risk_level"), "creator template missing source governance columns");
assert(files.creatorTemplate.includes("profile_image_url,channel_image_url"), "creator template missing visual identity columns");
assert(files.postsTemplate.includes("creator_id,platform_video_id,url,caption,transcript"), "recent posts template missing post analysis columns");
assert(files.postsTemplate.split(/\r?\n/).filter(Boolean).length >= 21, "recent posts template should include 20 sample rows");
assert(!files.html.includes("\uFFFD") && !files.app.includes("\uFFFD"), "replacement characters found in dashboard source");
requiredViews.forEach((view) => assert(files.html.includes(view), `missing ${view}`));
requiredEndpoints.forEach((endpoint) =>
  assert(files.client.includes(endpoint) || files.app.includes(endpoint), `missing ${endpoint}`)
);
[
  "assets/creator-luz.svg",
  "assets/creator-andrea.svg",
  "assets/creator-rutina.svg",
  "assets/channel-luz.svg",
  "assets/channel-andrea.svg",
  "assets/channel-rutina.svg",
].forEach((asset) => assert(existsSync(join(root, asset)), `missing ${asset}`));
assert(!files.app.includes("autoSend"), "automatic send hook must not exist");
assert(!files.html.includes("Mock Mode") && !files.app.includes("Mock Mode"), "dashboard should use Preview Mode wording");
assert(!files.html.includes("example.com") && !files.app.includes("example.com"), "dashboard source should avoid generic example.com demo URLs");
assert(!files.app.includes("briwell.example"), "dashboard should avoid generic example tracking domains");
assert(files.css.includes("@media (max-width: 680px)"), "mobile media query missing");
JSON.parse(files.vercel);

// --- Live-write safety gate (audit #11: distinguish real writes from local preview fallbacks) ---
assert(files.client.includes("setWriteGate"), "api-client write gate registration missing");
assert(files.client.includes("writeGate"), "api-client write gate variable missing");
assert(files.client.includes("error.cancelled = true"), "api-client cancelled error flag missing");
assert(files.client.includes("cancelled_by_user"), "api-client cancelled payload status missing");
assert(files.app.includes("window.BriwellApi.setWriteGate(writeGate)"), "app.js must register the write gate on load");
assert(files.app.includes("async function writeGate("), "app.js writeGate implementation missing");
assert(files.app.includes("WRITE_CONFIRM_ALLOWLIST"), "write confirm allowlist missing");
assert(files.app.includes("/outreach/claims-check") && files.app.includes("/operations/outreach-crm/board"), "write confirm allowlist must include pure-compute endpoints");
assert(files.app.includes("WRITE_CONFIRM_SUPPRESS_MS"), "10-minute write confirm suppression missing");
assert(files.app.includes("isWriteConfirmSuppressed"), "write confirm suppression check missing");
assert(files.app.includes("error.cancelled"), "app.js handlers must branch on error.cancelled to avoid local-preview fallback on cancel");

// Live write confirmation modal markup + accessibility pattern
assert(files.html.includes('id="writeConfirmModal"'), "write confirm modal mount missing");
assert(files.html.includes('role="dialog"') , "write confirm modal must use role=dialog");
assert(files.html.includes('aria-modal="true"'), "write confirm modal must use aria-modal");
assert(files.html.includes("실제 서버에 기록됩니다"), "write confirm modal title copy missing");
assert(files.html.includes('id="writeConfirmProceedButton"'), "write confirm proceed action missing");
assert(files.html.includes('id="writeConfirmCancelButton"'), "write confirm cancel action missing");
assert(files.html.includes("10분간 다시 묻지 않기"), "10-minute suppress checkbox copy missing");
assert(files.app.includes("Escape") && files.app.includes("onCancel"), "write confirm modal must cancel on Escape");
assert(files.app.includes("trapFocus"), "write confirm modal must trap focus");

// Data-state banner/pill dynamic 3-state model (live / preview, reflecting persisted vs validated_not_persisted at result level)
assert(files.app.includes("라이브 모드 · 쓰기 작업이 실제 서버에 기록됩니다"), "live mode banner copy missing");
assert(files.app.includes("미리보기 모드 · 목업 데이터 (정산 반영 안 됨)"), "preview mode banner copy missing");
assert(files.css.includes("is-live"), "live data-state styling missing");
assert(files.app.includes("updateWriteActionChips"), "write-action chip updater missing");
assert(files.css.includes("[data-write-action]"), "write-action chip styling missing");
const writeActionButtonCount = (files.html.match(/data-write-action/g) || []).length;
assert(writeActionButtonCount >= 10, `expected at least 10 data-write-action buttons, found ${writeActionButtonCount}`);

// Result chip states (showResult enhancement)
assert(files.app.includes("resolveResultChip"), "result chip resolver missing");
assert(files.app.includes("실제 서버 DB에 기록됨"), "persisted result chip copy missing");
assert(files.app.includes("검증만 됨") && files.app.includes("DB 비활성"), "validated_not_persisted result chip copy missing");
assert(files.app.includes("미리보기 · 서버에 반영 안 됨"), "preview result chip copy missing");
assert(files.app.includes("취소됨 · 아무것도 기록되지 않음"), "cancelled result chip copy missing");
assert(files.css.includes(".result-chip"), "result chip styling missing");

// Initial-load connectivity race (adversarial review finding #1): writeGate must
// fail-closed (force the confirm modal) until the first health check resolves,
// instead of trusting the apiOnline=false default and silently allowing writes.
assert(files.app.includes("apiConnectivityChecked"), "apiConnectivityChecked state flag missing");
assert(
  /if\s*\(!state\.apiConnectivityChecked\)\s*return openWriteConfirmModal/.test(files.app),
  "writeGate must force the confirm modal while connectivity is still unknown"
);
assert(
  /apiOnline = true;\s*\n\s*state\.apiConnectivityChecked = true;/.test(files.app) &&
    /apiOnline = false;\s*\n\s*state\.apiConnectivityChecked = true;/.test(files.app),
  "refreshFromApi must mark connectivity checked on both success and failure paths"
);

// Operations pipeline single-confirmation + cancel-stops-pipeline (finding #2):
// a multi-step write pipeline must ask once up front (not once per step) and
// must stop dead the moment any step reports cancelled_by_user.
assert(files.app.includes("confirmOperationsPipelineWrite"), "single up-front pipeline confirmation missing");
assert(files.app.includes("pipelineWriteApprovalActive"), "pipeline write approval token missing");
assert(
  /if\s*\(pipelineWriteApprovalActive\)\s*return true;/.test(files.app),
  "writeGate must honor the pipeline approval token so per-step writes are not re-prompted"
);
assert(files.app.includes("function stopOperationsPipelineOnCancel"), "pipeline cancel-stop helper missing");
const pipelineCancelCheckCount = (files.app.match(/stopOperationsPipelineOnCancel\(/g) || []).length;
assert(
  pipelineCancelCheckCount >= 7,
  `expected operations pipeline to check stopOperationsPipelineOnCancel after every step (>=7 call sites), found ${pipelineCancelCheckCount}`
);
assert(
  /pipelineWriteApprovalActive = true;[\s\S]*?finally[\s\S]*?pipelineWriteApprovalActive = false;/.test(files.app),
  "pipeline approval token must be released in a finally block after the run"
);

// sessionStorage access must not throw in private/blocked-storage contexts
// (finding #3), or the write gate throws before ever reaching the modal and
// live writes get silently mislabeled as local preview.
assert(
  /function isWriteConfirmSuppressed\(\)\s*{\s*try\s*{[\s\S]*?catch/.test(files.app),
  "isWriteConfirmSuppressed must guard sessionStorage access with try/catch"
);
assert(
  /function suppressWriteConfirmFor\([^)]*\)\s*{\s*try\s*{[\s\S]*?catch/.test(files.app),
  "suppressWriteConfirmFor must guard sessionStorage access with try/catch"
);

// Allowlisted (pure-compute) write buttons must not carry the LIVE/PREVIEW
// write-action badge, which implies a gated real write (finding #4).
assert(!files.html.includes('id="claimsCheckButton" data-write-action'), "claims-check button must not use the write-action (LIVE/PREVIEW) badge");
assert(files.html.includes('id="claimsCheckButton" data-compute-action'), "claims-check button must use the compute-action badge instead");
assert(files.css.includes("[data-compute-action]"), "compute-action badge styling missing");

console.log("dashboard smoke passed");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
