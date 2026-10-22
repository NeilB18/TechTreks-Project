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
