# Setting up Google sign-in

Sign-in only proves who you are; your budget stays private to you. You need a
Google Cloud OAuth client (free).

1. Go to https://console.cloud.google.com/, create a project (e.g. "tripbot").
2. Open **Google Auth Platform** (APIs & Services → OAuth consent screen) and fill in
   the app name and support email. Audience: **External**. While testing, add your
   team's Google accounts as test users.
3. Go to **Clients → Create client** → type **Web application**.
4. Add the authorized redirect URI. It's on the **trip page's** host, because the page
   proxies `/accounts/` to Django so the sign-in cookie lands on the page's domain:
   - local: `http://localhost:3000/accounts/google/login/callback/`
   - production: `https://<trip page host>/accounts/google/login/callback/`
5. Copy the client ID and secret into `.env` (never commit it):
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   FRONTEND_URL=http://localhost:3000
   ```
6. Run the trip page with `TRIP_API_URL` pointing at Django (see web/README.md) and sign
   in from a trip page. Django must be reachable only through the page's proxy in
   production, because it trusts the `X-Forwarded-Host` header the proxy sets.

## How linking works

Google tells us who you are, but not which person you are in the GroupMe chat. So:

1. Sign in on the trip page; it shows a 6-character code (`POST /api/me/link-code`).
2. Post `@tripbot link <code>` in the trip's group chat within 15 minutes.
3. The bot sees which GroupMe account posted it and links that trip member to your sign-in.

After that, `GET /api/me/trips/<trip_id>/budget` returns your budget and any private
notices, and only yours. This works even if GroupMe DMs don't.
