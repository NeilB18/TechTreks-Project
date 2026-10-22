# Trip page (Next.js)

The page the bot links to: itinerary by day, who owes whom (with Venmo pay links),
and expenses. Budgets are private, so they never appear here; the "My budget" panel
gets wired to sign-in later.

```bash
npm install
npm run dev        # http://localhost:3000/trips/miami-demo
npm test           # Vitest
npm run lint && npm run build
```

## Data

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
3. once you're linked, shows your own total, spent, planned, what's left, warnings,
   and private messages from @tripbot.

Setup: [../docs/google-signin.md](../docs/google-signin.md).
