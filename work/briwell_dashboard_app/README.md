# Briwell Operator Dashboard

Static dashboard scaffold for Briwell creator operations.

The dashboard can run as a local file, a static web server, or a Vercel static
site. It connects to the FastAPI backend when available and uses a local
preview dataset when the API is offline.

## Files

```text
index.html
styles.css
api-client.js
app.js
templates/creator_candidates_template.csv
templates/recent_posts_20_template.csv
vercel.json
tests/smoke.mjs
```

## Local Preview

Open `index.html` in a browser.

Optional local static server:

```bash
python -m http.server 8070
```

Then open:

```text
http://127.0.0.1:8070
```

## Backend Connection

The default API URL is:

```text
http://127.0.0.1:8030
```

The dashboard sends development RBAC headers:

```text
X-User-Role: admin
X-User-Email: operator@briwell.test
```

For production OIDC, the next dashboard iteration should exchange Supabase Auth
session tokens and send:

```text
Authorization: Bearer <supabase-jwt>
```

## Implemented Workflows

1. API health and readiness summary
2. Source policy display
3. AI provider status display
4. MX/PE/EC candidate inbox and filters
5. Discovery plan generation
6. Discovery coverage audit and recall safeguards
7. Downloadable creator candidate CSV template and `/creators/import` handoff
8. Downloadable recent 20 posts CSV template, manual intake, and `/videos/import` handoff
9. Upload validation report for column contract, source governance, recent-post readiness, and DB E2E gate
10. Growth Operations Engine for import logging, enrichment, recent-post apply, campaign match, outreach plan, CRM board, and performance rollup
11. Recent 20 posts screening via `/analysis-jobs/run-recent-posts-screen`
12. Campaign draft creation
13. Campaign outreach draft preparation
14. DM claims check and human approval gate
15. Manual send status recording
16. Performance snapshot capture
17. Settlement contract capture

## Executive Overview Standard

The first screen is intentionally commerce-led instead of system-led. It should
prioritize pipeline GMV forecast, recent-20 data coverage, outreach-ready
talent, human review load, funnel bottlenecks, and operator next actions. API
health remains visible as an operational signal, but it should not displace the
commercial decision layer.

## Vercel

Deploy this directory as a static project. The API base URL can later be moved
to an environment-backed runtime config or a small Next.js wrapper.

## Validation

```bash
node tests/smoke.mjs
```
