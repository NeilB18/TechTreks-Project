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
this site's domain, and `components/trip/MemberData.tsx` loads `/api/me/trips/<id>` once in the
browser for both tabs. The page:

1. offers "Sign in with Google" when you're signed out;
2. once you're signed in, gives you a code to post as `@tripbot link <code>` in the group;
3. once you're linked to a member of the trip, shows settle-up, expenses, the group budget,
   and your own total, spent, planned, what's left and warnings.

In fixtures mode there's no sign-in, so the fixture's sample money is shown to everyone.

Setup: [../docs/google-signin.md](../docs/google-signin.md).

## Pages

- `/`: the landing page (in sample mode it also lists the sample trips).
- `/t/<share_token>`: the trip page's Trip tab. Details (with Add to calendar, an `.ics` made in the browser), Your money, Latest and the plan. Your money, Latest and where you're staying only show for people on the trip. In sample mode the token is the fixture's name, and a "Preview as" bar shows the page as someone signed out, someone not on the trip, or any member (`?as=`); the theme picker previews with `?theme=`.
- `/t/<share_token>/money`: the Money tab (people on the trip only): settle up, budgets, and everything spent.
- `/trips`: My trips (`GET /api/me/trips`): coming up, past, and "Missing a trip?".
- `/link`: get a link code, post it in the group, and the page opens the trip once the bot sees it.

## Look and themes

The site is called TravelBot for now (`lib/site.ts`, one constant; the bot stays @tripbot). It
uses one dark background and Mona Sans (`next/font`, with its width axis for titles). The designs
are on the "Final designs" page of the redesign canvas; the brief and the banned list are in
[../docs/design-brief.md](../docs/design-brief.md).

Each trip has a theme: one of our own photos, shown behind the trip's title and blurred behind the
page, plus one accent colour (`lib/themes.ts`, `app/globals.css`). The bot picks it from the
destination and people on the trip can change it. There are no uploads.

| Theme | Bot id | Photo (Unsplash) |
|---|---|---|
| Beach | `sunset` | Rolando Yera, [palms at sunset](https://unsplash.com/photos/ATwi-EmGbSE) |
| City nights | `night_swim` | Adam Borkowski, [downtown street at night](https://unsplash.com/photos/s1oMlP-RlqU) |
| Mountains | `campfire` | Chris Ried, [Smoky Mountain ridges](https://unsplash.com/photos/D2NvTDuPME4) |
| Snow | `snow` | Devin Lyster, [pines in front of snowy peaks](https://unsplash.com/photos/uKnFVOAMQq0) |
| Desert road | `desert` | Shinichiro Ichimura, [desert road](https://unsplash.com/photos/i87kxNbAD0E) |

The photos are free under the [Unsplash License](https://unsplash.com/license) (no credit required;
we credit anyway). Snow and Desert road show on the site already, but the picker only offers them
once the bot can save them (`pickable` in `lib/themes.ts`).

To see everything on your own computer without the bot: `npm install && npm run dev`, then open `http://localhost:3000`. To check on a phone, open the "Network" address `npm run dev` prints, on the same Wi-Fi.
