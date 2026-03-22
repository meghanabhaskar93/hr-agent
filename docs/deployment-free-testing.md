# Free Deployment For Friend Testing (Render + Optional Cloudflare Access)

This guide deploys:
- `pinghr-api` (FastAPI backend) on Render free web service.
- `pinghr-ui` (React/Vite frontend) on Render free static site.

It also includes a basic tester gate using `ALLOWED_TEST_USER_EMAILS`.

## 1. Prerequisites

- GitHub repo pushed with this branch.
- A Render account.
- LLM credentials ready:
  - `LLM_API_KEY`
  - Optional `LLM_BASE_URL`
  - Optional `LLM_MODEL` override

## 2. Deploy With Blueprint

1. In Render, click `New` -> `Blueprint`.
2. Connect this GitHub repo.
3. Select branch (for example: `feature-ui-new-typescript`).
4. Render reads `render.yaml` and proposes 2 services:
   - `pinghr-api`
   - `pinghr-ui`
5. Create both services.

## 3. Configure API Secrets

In Render -> `pinghr-api` -> `Environment`:

- Set `LLM_API_KEY` (required).
- Set `LLM_BASE_URL` if using OpenAI-compatible non-default endpoint.
- Update `ALLOWED_TEST_USER_EMAILS` to your tester list (comma-separated).
- Set Turso DB credentials for persistent data:
  - `TURSO_DATABASE_URL` (required for deployment persistence)
  - `TURSO_AUTH_TOKEN`

Example:

```text
amanda.foster@acme.com,jordan.lee@acme.com,alex.kim@acme.com
```

Only these emails can access the API.

### Optional: Migrate Existing Local SQLite Data to Turso

If you already have data in local `hr_demo.db`, migrate once before switching Render to Turso:

```bash
python scripts/migrate_sqlite_to_turso.py \
  --source ./hr_demo.db \
  --target-url "$TURSO_DATABASE_URL" \
  --target-token "$TURSO_AUTH_TOKEN"
```

## 4. Point UI To Real API URL

After `pinghr-api` is live, copy its Render URL.

In Render -> `pinghr-ui` -> `Environment`:
- Set `VITE_API_BASE_URL` to your real API URL.

Example:

```text
https://pinghr-api.onrender.com
```

Then trigger a manual redeploy of `pinghr-ui`.

## 5. Verify

1. Open UI URL from `pinghr-ui`.
2. Log in with an allowlisted email.
3. Send a chat message and confirm response.
4. Try a non-allowlisted email and confirm it is blocked.

## 6. Optional: Add Cloudflare Access

If you have a custom domain on Cloudflare:

1. Put your Render UI behind a Cloudflare-managed hostname.
2. In Cloudflare Zero Trust -> Access -> Applications, add a self-hosted app.
3. Add an allow policy with only your friends' emails.
4. Add a deny fallback policy for everyone else.

This gives an external access gate in addition to the API email allowlist.

## Notes

- Render free services may spin down when idle.
- Current session/chat memory is in-process and not durable across restarts.
- Turso persistence covers database-backed entities (requests, escalations, employees, policies, etc.).
