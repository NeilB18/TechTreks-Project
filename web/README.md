# Trip page (Next.js)

The page the bot links to. Anyone with the link sees the overview and the itinerary by day.
Signed-in members of the trip also see who owes whom (with Venmo pay links), expenses, the
group budget and their own budget.

```bash
npm install
npm run dev        # http://localhost:3000/t/miami-demo (in fixtures mode the link is the fixture name)
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
open the `/t/<share_token>` link that `seed_demo_trip` prints. The live home page does not list
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

## Sign-in and the money side

With `TRIP_API_URL` set, the server renders the overview and itinerary from
`/api/share/<share_token>` (the page is `/t/<share_token>`), which has no money in it. The page proxies `/accounts/*`
(Google sign-in) and `/api/me/*` to Django (see `proxy.ts`), so the session cookie is on
this site's domain, and the money section (`components/MoneySection.tsx`) loads
`/api/me/trips/<id>` in the browser. It:

1. offers "Sign in with Google" when you're signed out;
2. once you're signed in, gives you a code to post as `@tripbot link <code>` in the group;
3. once you're linked to a member of the trip, shows settle-up, expenses, the group budget,
   and your own total, spent, planned, what's left and warnings.

In fixtures mode there's no sign-in, so the fixture's sample money is shown to everyone.

Setup: [../docs/google-signin.md](../docs/google-signin.md).

## Pages

- `/`: the landing page (in sample mode it also lists the sample trips).
- `/t/<share_token>`: a trip page. In sample mode the token is the fixture's name, and a "Preview as" bar shows the page as someone signed out, someone not on the trip, or any member (`?as=`); the theme picker previews with `?theme=`.
- `/trips`: My trips (`GET /api/me/trips`): coming up, past, and "Missing a trip?".
- `/link`: get a link code, post it in the group, and the page opens the trip once the bot sees it.

To see everything on your own computer without the bot: `npm install && npm run dev`, then open `http://localhost:3000`. To check on a phone, open the "Network" address `npm run dev` prints, on the same Wi-Fi.
