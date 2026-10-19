# Pahunch

Pahunch is a learning-oriented, full-stack public-benefits portal. Citizens can discover schemes, check profile-based eligibility, review document checklists, apply, and follow application updates. It also includes a transparent, rules-based scheme assistant.

## Run locally

Requirements: Node.js 20+, npm, and Python 3.10+.

1. Install frontend dependencies: `npm install`
2. Install API dependencies: `python -m pip install -r requirements.txt`
3. Start the API in one terminal: `python -m uvicorn backend.main:app --reload`
4. Start the portal in another terminal: `npm run dev`
5. Open the URL printed by Vite (usually `http://localhost:5173`).

Demo account (local SQLite mode only): **demo@pahunch.in** / **Pahunch123!**

Interactive API docs are at `http://localhost:8000/api/v1/docs`. The first API start creates `backend/data/pahunch.db` and seeds example schemes and the demo account.

## Deploy frontend, API, and database

The repository is configured for **Neon PostgreSQL + Render (API) + Vercel (frontend)**. Keep the Neon connection string private: only configure it as the backend's `DATABASE_URL` secret. Never add it to the frontend or commit it to Git.

1. Push this project to a GitHub repository.
2. In Neon, create a PostgreSQL project and copy its pooled connection string. Keep it private; do not paste it into a public issue, source file, or frontend variable.
3. In Render, create a **Web Service** from the GitHub repository and use the included `render.yaml` blueprint (or enter the commands shown there). Set `DATABASE_URL` to the Neon connection string and `PAHUNCH_CORS_ORIGINS` temporarily to `http://localhost:5173`. Render generates `PAHUNCH_JWT_SECRET` from the blueprint. Deploy, then check `https://<your-render-service>.onrender.com/api/v1/health`.
4. In Vercel, import the same GitHub repository. Set the build output to `dist` (the included `vercel.json` already configures Vite) and add `VITE_API_URL` with the Render service origin, for example `https://pahunch-api.onrender.com` (no `/api/v1` suffix). Deploy.
5. Set Render's `PAHUNCH_CORS_ORIGINS` to your exact Vercel site origin, for example `https://pahunch.vercel.app` (no trailing slash), and redeploy the API.
6. Open the Vercel URL and create a citizen account. Hosted deployments intentionally do **not** seed the public demo account. Example scheme records are seeded automatically on first API startup.

The API creates the PostgreSQL tables and example schemes automatically on first start. `DATABASE_URL` unset means local SQLite remains in use. Existing accounts and applications in a local SQLite file are **not automatically copied** to Neon; back up and migrate them separately before moving an existing installation. Neon connection strings and JWT secrets should only be entered in provider dashboards as private environment variables.

After deployment, the API docs are available at `https://<your-render-service>.onrender.com/api/v1/docs`. Use a database backup before schema or data changes, and rotate secrets if they are ever exposed.

## What is included

- React + Vite responsive portal with overview, searchable scheme directory, application tracker, profile editor, and assistant.
- FastAPI REST API under `/api/v1` with OpenAPI docs, pagination, filtering, sorting, validation, and resource-appropriate HTTP errors.
- SQLite (local) or Neon PostgreSQL (hosted) relational schema for users, profiles, schemes, applications, and application events, with foreign keys, constraints, and access-pattern indexes.
- PBKDF2 password hashing, expiring signed JWT bearer tokens, citizen/admin role checks, and a basic in-memory per-IP rate limit.
- Profile-based eligibility matching, document requirements, duplicate application protection, reference numbers, status history, and admin-only status updates.
- Short-lived in-memory cache for scheme catalogue results. The cache is intentionally small and process-local for the single-instance teaching setup.
- Seven API tests covering authentication, scheme search and eligibility, application tracking, profile updates, assistant responses, and hosted database safeguards.

## API examples

Authenticate with `POST /api/v1/auth/login`; send the returned token as `Authorization: Bearer <token>`.

- `GET /api/v1/schemes?q=health&category=Healthcare&page=1&page_size=12&sort=featured`
- `GET /api/v1/eligibility`
- `GET` / `PUT /api/v1/profile`
- `GET` / `POST /api/v1/applications`
- `PATCH /api/v1/applications/{id}` to withdraw your own application
- `PATCH /api/v1/admin/applications/{id}/status` for administrators
- `POST /api/v1/assistant/chat`

GET is safe; application creation is POST; profile replacement is PUT; application withdrawal and admin status changes are PATCH operations. Duplicate applications are rejected with 409, missing resources with 404, invalid data with 422, and unauthenticated requests with 401.

## Run the API tests

```sh
py -3.12 -m unittest discover -s tests -v
```

The API tests use a temporary SQLite database, so they do not change the local demo database.

## Curriculum map and design choices

- **REST/API design:** versioned resource URLs, GET/POST/PUT/PATCH, idempotent profile replacement, status/error conventions, query filters, sort, pagination, Pydantic validation, and generated OpenAPI docs. The current login is a first-party demo flow; OAuth 2.0 authorization-code and client-credentials integrations can be added when an identity provider or service client is selected.
- **Database design:** normalized SQLite/PostgreSQL tables with PK/FK constraints, unique application-per-scheme protection, indexes, and parameterized queries. SQL is a good fit for citizen profiles and applications because eligibility and application transitions benefit from constraints and transactions. A document store could suit flexible scheme metadata, Redis could hold shared cache/rate-limit state, and Cassandra is not justified for this demo's transactional access patterns. The current schema bootstrap is idempotent; a production rollout should use versioned migrations.
- **Auth/security:** signed, expiring JWTs, salted PBKDF2 password hashes, citizen/admin role checks, request validation, and rate limiting. This demo sends bearer tokens from the browser. For production, replace the development JWT secret, use HTTPS and secure HttpOnly cookies or a managed identity provider, and add CSRF protection if cookie authentication is enabled.
- **Scaling/caching:** the scheme catalogue uses a short TTL cache-aside pattern, with in-process rate limiting. These are single-process teaching implementations, not shared infrastructure. A multi-worker deployment should use Redis for shared cache/rate-limit state, a reverse proxy/load balancer such as NGINX, database read replicas where needed, and a CDN for static assets. Cache invalidation is not needed for the read-only seeded catalogue; mutable scheme administration would need explicit invalidation.
- **Frontend:** React components, JSX, hooks, local state, asynchronous `fetch` calls, loading/error states, and responsive CSS Grid/Flexbox. Semantic forms, labels, keyboard focus styles, status announcements, and reduced-motion support are included. React Query/Redux are deliberately not added for this small client; they become useful as shared client state and background revalidation needs grow.
- **Testing/docs:** API behavior is exercised with automated FastAPI tests, and interactive Swagger/OpenAPI docs are available at `/api/v1/docs`.

## Important demo limitations

Scheme data is illustrative, eligibility results are indicative (not an official decision), and the assistant is a transparent rules-based demo—not a generative AI model. Verify scheme details with the relevant government department before relying on them. The included local demo credentials, in-memory rate limiter/cache, and SQLite database are not production settings. Admin status changes require an account whose `role` is set to `admin` in the database. Hosted deployments must use a private Neon connection string and a unique strong JWT secret.
