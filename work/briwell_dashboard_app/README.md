# Briwell Operator Dashboard

Static dashboard scaffold for Briwell creator operations.

The dashboard can run as a local file, a static web server, or a Vercel static
site. It connects to the FastAPI backend when available and falls back to mock
data when the API is offline.

## Files

```text
index.html
styles.css
api-client.js
app.js
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
6. Campaign draft creation
7. Campaign outreach draft preparation
8. DM claims check and human approval gate
9. Manual send status recording
10. Performance snapshot capture
11. Settlement contract capture

## Vercel

Deploy this directory as a static project. The API base URL can later be moved
to an environment-backed runtime config or a small Next.js wrapper.

## Validation

```bash
node tests/smoke.mjs
```
