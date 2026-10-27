"""Agent-side additions to tool results, so the model quotes real numbers.

Live runs showed qwen3.8-flash misreading cents as dollars (MX$18 instead of
MX$1,800, "$30" instead of "$300") and pointing debtors at the wrong payment
handle. Rather than change the engine, the runner adds chat-ready text next to
the raw numbers:
- `display`: formatted amounts (totals, shares, per-person, balances)
- `lines`: settle-up lines from `suggested_payments`, using the receiver's handle
"""

SYMBOLS = {"USD": "$", "MXN": "MX$", "EUR": "€", "GBP": "£", "CAD": "CA$"}
PERSON_MAPS = ("shares", "per_person")  # person_id -> cents, never negative
SIGNED_MAPS = ("splits", "net_balances")  # person_id -> cents, + is owed, - owes


def fmt_money(cents: int, currency: str = "USD", signed: bool = False) -> str:
    """3336 -> "$33.36", 180000 MXN -> "MX$1,800", signed -1300 -> "-$13"."""
    text = f"{SYMBOLS.get(currency, currency + ' ')}{abs(cents) / 100:,.2f}".replace(".00", "")
    if cents < 0:
        return "-" + text
    return ("+" + text) if signed and cents > 0 else text


def enrich(result: dict, args: dict, summary: dict) -> dict:
    """Add `display` (and `lines` for settle-up suggestions) to a tool result. Returns the same dict."""
    currency = result.get("base_currency") or result.get("currency") or summary["trip"].get("base_currency", "USD")
    members = {m["id"]: m for m in summary["members"]}
    name = lambda pid: members.get(pid, {}).get("name", pid)  # noqa: E731
    display: dict = {}
    if isinstance(result.get("base_amount"), int):
        display["amount"] = fmt_money(result["base_amount"], currency)
        orig_ccy = result.get("original_currency")
        if orig_ccy and orig_ccy != currency and isinstance(result.get("original_amount"), int):
            display["original_amount"] = fmt_money(result["original_amount"], orig_ccy)
    for key in PERSON_MAPS + SIGNED_MAPS:
        if isinstance(result.get(key), dict):
            display[key] = {pid: fmt_money(c, currency, signed=key in SIGNED_MAPS)
                            for pid, c in result[key].items() if isinstance(c, int)}
    payer = args.get("paid_by")
    if payer in members:
        handle = members[payer].get("handle")
        # The people in the split pay the payer, so it's the payer's handle, never the debtor's.
        display["pay_to"] = f"{name(payer)} ({handle})" if handle else name(payer)
    if isinstance(result.get("suggested_payments"), list):
        result["lines"] = [
            f"{name(p['from'])} pays {name(p['to'])} {fmt_money(p['amount_cents'], currency)}"
            + (f", {p['handle']}" if p.get("handle") else "")
            for p in result["suggested_payments"]]
    if display:
        result["display"] = display
    return result
