"""SerpAPI Google Hotels client (engine=google_hotels), for lodging prices."""

import requests

URL = "https://serpapi.com/search.json"


def hotels(api_key: str, query: str, check_in: str, check_out: str, adults: int = 2,
           currency: str = "USD", max_price: int | None = None, limit: int = 3,
           timeout: float = 15) -> list[dict]:
    """Cheapest-first stays, simplified. Dates are YYYY-MM-DD. Raises on problems (callers fall back)."""
    params = {"engine": "google_hotels", "q": query, "check_in_date": check_in,
              "check_out_date": check_out, "adults": adults, "currency": currency,
              "sort_by": 3, "api_key": api_key}
    if max_price:
        params["max_price"] = max_price
    resp = requests.get(URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    out = []
    for p in data.get("properties", []):
        nightly = (p.get("rate_per_night") or {}).get("extracted_lowest")
        if nightly is None:
            continue
        out.append({"name": p["name"], "type": p.get("type"), "per_night_cents": round(nightly * 100),
                    "total_cents": round(((p.get("total_rate") or {}).get("extracted_lowest") or 0) * 100),
                    "rating": p.get("overall_rating")})
    return out[:limit]
