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
  "/campaigns",
  "/outreach/claims-check",
  "/outreach/status-transition",
  "/performance/snapshots",
  "/settlements/contracts",
];

assert(files.html.includes("Briwell Creator Commerce Intelligence"), "missing global dashboard title");
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
assert(files.html.includes("postCsvInput"), "missing recent posts CSV upload input");
assert(files.html.includes("manualPostsInput"), "missing manual recent posts input");
assert(files.html.includes("runRecentScreenButton"), "missing recent 20 posts screen action");
assert(files.html.includes("Import Quality Gate"), "missing import quality gate");
assert(files.html.includes("importQualityGate"), "missing import quality gate mount");
assert(files.html.includes("coverageAudit"), "missing coverage audit mount");
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
assert(files.css.includes(".quality-gate"), "import quality gate styling missing");
assert(files.css.includes(".quality-summary"), "quality summary styling missing");
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
assert(files.app.includes("saveImportQualityLog"), "import quality operations API missing");
assert(files.app.includes("matchCampaignCandidates"), "campaign match operations API missing");
assert(files.app.includes("evaluateImportQuality"), "import quality evaluator missing");
assert(files.app.includes("validateCreatorDataset"), "creator quality validation missing");
assert(files.app.includes("validateRecentPostDataset"), "recent post quality validation missing");
assert(files.app.includes("parseCsv"), "CSV parser missing");
assert(files.app.includes("runRecentScreenForCreator"), "recent posts screen workflow missing");
assert(files.app.includes("coverageAudit"), "coverage audit state missing");
assert(files.app.includes("Shortlist Talent"), "shortlist action missing");
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
assert(files.css.includes("@media (max-width: 680px)"), "mobile media query missing");
JSON.parse(files.vercel);

console.log("dashboard smoke passed");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
