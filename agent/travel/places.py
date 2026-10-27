"""Google Places API (New) Text Search client.

POST https://places.googleapis.com/v1/places:searchText with X-Goog-Api-Key and an
X-Goog-FieldMask. Asking for rating/priceLevel bills at the Enterprise SKU.
"""

import requests

URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.displayName", "places.formattedAddress", "places.rating",
    "places.userRatingCount", "places.priceLevel", "places.googleMapsUri",
])
PRICE_LEVELS = ["PRICE_LEVEL_INEXPENSIVE", "PRICE_LEVEL_MODERATE",
                "PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]


def search(api_key: str, text: str, price_levels: list[str] | None = None,
           included_type: str | None = None, page_size: int = 5, timeout: float = 10) -> list[dict]:
    """Places matching `text`, simplified. Raises on any HTTP or shape problem (callers fall back)."""
    body: dict = {"textQuery": text, "pageSize": page_size}
    if price_levels:
        body["priceLevels"] = price_levels
    if included_type:
        body["includedType"] = included_type
    resp = requests.post(URL, json=body, timeout=timeout, headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK})
    resp.raise_for_status()
    out = []
    for p in resp.json().get("places", []):
        out.append({
            "name": p["displayName"]["text"],
            "address": p.get("formattedAddress"),
            "rating": p.get("rating"),
            "ratings": p.get("userRatingCount"),
            "price_level": p.get("priceLevel"),
            "maps_url": p.get("googleMapsUri"),
        })
    return out
