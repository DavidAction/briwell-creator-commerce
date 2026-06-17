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
];

assert(files.html.includes("Briwell Creator Commerce Intelligence"), "missing global dashboard title");
assert(files.html.includes("글로벌 MCN 운영 콘솔"), "missing Korean executive positioning copy");
assert(files.html.includes("오늘 처리해야 할 최고 우선순위 액션"), "missing Korean operator action copy");
assert(files.html.includes("후보 업로드"), "missing Korean intake navigation copy");
assert(files.html.includes("Executive Overview"), "missing executive navigation");
assert(files.html.includes("Talent Intake"), "missing talent intake navigation");
assert(files.html.includes("Talent Intelligence"), "missing talent intelligence navigation");
assert(files.html.includes("Brand Safety Desk"), "missing brand safety navigation");
assert(files.html.includes("No Auto-Send"), "manual-send safety gate missing");
assert(files.html.includes("Pipeline GMV Forecast"), "missing commerce forecast metric");
assert(files.html.includes("Recent-20 Coverage"), "missing recent 20 coverage metric");
assert(files.html.includes("Commerce Command Board"), "missing commerce command board");
assert(files.html.includes("Operator Next Actions"), "missing operator action queue");
assert(files.html.includes("Growth Operations Engine"), "missing operations engine");
assert(files.html.includes("runOperationsPipelineButton"), "missing operations pipeline action");
assert(files.html.includes("Creator Portfolio Leaders"), "missing visual portfolio leaders");
assert(files.html.includes("creatorCsvInput"), "missing creator CSV upload input");
assert(files.html.includes("downloadCreatorTemplateButton"), "missing creator CSV template download");
assert(files.html.includes("postCsvInput"), "missing recent posts CSV upload input");
assert(files.html.includes("downloadPostTemplateButton"), "missing recent posts template download");
assert(files.html.includes("manualPostsInput"), "missing manual recent posts input");
assert(files.html.includes("recentScreenMode"), "missing recent screen AI mode selector");
assert(files.html.includes("recentScreenModeHint"), "missing recent screen live-readiness hint");
assert(files.html.includes("Live Gemini Analysis"), "missing live Gemini screening option");
assert(files.html.includes("runRecentScreenButton"), "missing recent 20 posts screen action");
assert(files.html.includes("Import Quality Gate"), "missing import quality gate");
assert(files.html.includes("importQualityGate"), "missing import quality gate mount");
assert(files.html.includes("coverageAudit"), "missing coverage audit mount");
assert(files.html.includes("TikTok Provider Acquisition"), "missing TikTok provider acquisition panel");
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
assert(files.app.includes("Shortlist Talent"), "shortlist action missing");
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

console.log("dashboard smoke passed");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
