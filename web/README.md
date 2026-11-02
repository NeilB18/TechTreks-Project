# Trip page (Next.js)

The page the bot links to: itinerary by day, who owes whom (with Venmo pay links),
and expenses. Budgets are shared with everyone on the trip; the "My budget" panel
gets wired to sign-in later.

```bash
npm install
npm run dev        # http://localhost:3000/trips/miami-demo
npm test           # Vitest
npm run lint && npm run build
```

## Data

### Local Supabase preview on Windows

Set `DATABASE_URL` in the repository-root `.env` to the Supabase PostgreSQL URI
with `sslmode=require`. Set a private `AGENT_API_TOKEN` there, too. Install the
root `requirements.txt` in your Python environment, then run from the repository root:

```powershell
.venv/Scripts/python.exe -X utf8 backend/manage.py migrate
.venv/Scripts/python.exe -X utf8 backend/manage.py seed_demo_trip
.venv/Scripts/python.exe -X utf8 backend/manage.py runserver 127.0.0.1:8000
```

The seed command creates `supabase-demo` with sample members, activities, expenses,
a refund, and a recorded payback. It leaves an existing trip unchanged. All payment
handles are sample values. It does not create signed-in accounts or link a GroupMe bot.

In `web/.env.local`, set `TRIP_API_URL=http://127.0.0.1:8000` and
`TRIP_API_TOKEN` to the same private token as Django. Both environment files are
gitignored. Start the frontend from `web/` with `npm run dev -- --webpack`, then
open `http://127.0.0.1:3000/trips/supabase-demo`. The live home page does not list
trips; use this direct link. Google sign-in requires the separate OAuth setup below.

- **Default: fixtures.** `fixtures/*.json` are generated from the real backend logic
  (`npm run fixtures` runs `scripts/export_fixtures.py`). One file per examples.md
  scenario, plus `miami-demo`.
- **Live API.** Set `TRIP_API_URL` (e.g. `http://localhost:8000`) and `TRIP_API_TOKEN`
  (the backend's `AGENT_API_TOKEN`). Both are read on the server only, so the token
  never reaches the browser.

  ```bash
  TRIP_API_URL=http://localhost:8000 TRIP_API_TOKEN=dev-agent-token npm run dev
  ```

## Sign-in and "My budget"

With `TRIP_API_URL` set, the page proxies `/accounts/*` (Google sign-in) and `/api/me/*`
to Django (see `next.config.ts`), so the session cookie is on this site's domain. The
"My budget" panel then:

1. offers "Sign in with Google";
2. once you're signed in, gives you a code to post as `@tripbot link <code>` in the group;
3. once you're linked, shows your own total, spent, planned, what's left and warnings.

Setup: [../docs/google-signin.md](../docs/google-signin.md).
