// Browser-side POSTs to the signed-in API (/api/me/*, proxied to Django with the session cookie).
// Django checks the CSRF token, which /api/me/ sets as a cookie.

export function csrfToken(): string {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ?? "";
}

/** POST JSON; resolves to the parsed reply, or throws an Error with Django's message. */
export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error ?? `Request failed (${res.status})`);
  return data as T;
}

/** "231.36" or "$231" -> 23136 cents; null if it isn't a plain amount. */
export function parseDollars(text: string): number | null {
  const m = text.trim().replace(/^\$/, "").replace(/,/g, "").match(/^(\d+)(?:\.(\d{1,2}))?$/);
  if (!m) return null;
  return Number(m[1]) * 100 + Number((m[2] ?? "").padEnd(2, "0"));
}
