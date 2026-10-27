import type { Activity, BudgetWarning } from "./types";

export function formatMoney(cents: number, currency = "USD"): string {
  const whole = cents % 100 === 0;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// ISO dates are calendar dates for the trip, so parse them without time zones.
function parts(iso: string) {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return { y, m, d };
}

export function formatDate(iso: string): string {
  const { m, d } = parts(iso);
  return `${MONTH[m - 1]} ${d}`;
}

export function formatDay(iso: string): string {
  const { y, m, d } = parts(iso);
  return `${WEEKDAY[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]}, ${MONTH[m - 1]} ${d}`;
}

export function formatDateRange(start: string | null, end: string | null): string | null {
  if (!start || !end) return start ? formatDate(start) : null;
  const a = parts(start);
  const b = parts(end);
  if (a.y === b.y && a.m === b.m) return `${MONTH[a.m - 1]} ${a.d}–${b.d}, ${a.y}`;
  if (a.y === b.y) return `${formatDate(start)} – ${formatDate(end)}, ${a.y}`;
  return `${formatDate(start)}, ${a.y} – ${formatDate(end)}, ${b.y}`;
}

export function formatTime(iso: string | null): string | null {
  if (!iso || iso.length <= 10) return null;
  const [h, min] = iso.slice(11, 16).split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return min ? `${hour}:${String(min).padStart(2, "0")}${suffix}` : `${hour}${suffix}`;
}

export type Day = { date: string | null; activities: Activity[] };

/** Activities grouped by calendar day in date/time order; undated ones last. */
export function groupByDay(activities: Activity[]): Day[] {
  const days = new Map<string, Activity[]>();
  const undated: Activity[] = [];
  for (const a of activities) {
    if (!a.start) {
      undated.push(a);
      continue;
    }
    const day = a.start.slice(0, 10);
    days.set(day, [...(days.get(day) ?? []), a]);
  }
  const out: Day[] = [...days.keys()].sort().map((date) => ({
    date,
    activities: days.get(date)!.sort((x, y) => (x.start ?? "").localeCompare(y.start ?? "")),
  }));
  if (undated.length) out.push({ date: null, activities: undated });
  return out;
}

export type PayLink =
  | { kind: "venmo"; href: string; label: string }
  | { kind: "other"; handle: string; label: string };

/**
 * Venmo handles ("@name") get a pay link with the amount filled in. Anything else
 * (an email or phone for Zelle) has no public pay link, so it's shown to copy.
 */
export function payLink(handle: string | null, cents: number, note: string): PayLink | null {
  if (!handle) return null;
  if (handle.startsWith("@")) {
    const user = encodeURIComponent(handle.slice(1));
    const params = new URLSearchParams({ txn: "pay", amount: (cents / 100).toFixed(2), note });
    return { kind: "venmo", href: `https://venmo.com/${user}?${params}`, label: `Pay on Venmo` };
  }
  return { kind: "other", handle, label: `Zelle / other: ${handle}` };
}

export function isOutsideTrip(a: Activity, start: string | null, end: string | null): boolean {
  if (!a.start || !start || !end) return false;
  const d = a.start.slice(0, 10);
  return d < start || d > end;
}

const CATEGORY_WORDS = /\b(LODGING|TRANSPORT|FOOD|DRINKS|ACTIVITIES|OTHER)\b/g; // trip_model Category names

/** A budget warning in plain words: "DRINKS under 10% remaining" -> "Drinks: under 10% left". */
export function warningText(w: BudgetWarning): string {
  let text = typeof w === "string" ? w : [w.category, w.message ?? w.text].filter(Boolean).join(" ");
  text = text.replace(CATEGORY_WORDS, (word) => {
    return word[0] + word.slice(1).toLowerCase();
  });
  text = text.replace(/^(\w[\w ]*?) (under|over) /, "$1: $2 ").replace(/ remaining\b/, " left");
  return text;
}
