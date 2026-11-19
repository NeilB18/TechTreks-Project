import type { Activity, BudgetWarning, Slot } from "./types";

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

/** "Aarav", "Aarav and Jake", "Leo, Priya and Sam". */
export function listNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** What to call a non-Venmo handle on its copy button. */
export function handleKind(handle: string): string {
  if (/^\S+@\S+\.\S+$/.test(handle)) return "email";
  if (/^[\d\s()+-]{7,}$/.test(handle)) return "number";
  return "handle";
}

/** "Sun, Mar 14 to Thu, Mar 18"; one date alone if there's no end. */
export function formatDayRange(start: string | null, end: string | null): string | null {
  if (!start) return null;
  if (!end || end === start) return formatDay(start);
  return `${formatDay(start)} to ${formatDay(end)}`;
}

function dayNumber(iso: string): number {
  const { y, m, d } = parts(iso);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

/**
 * How far off the trip is, from `today` (an ISO date): "124 days to go", "Tomorrow",
 * "Happening now", or null once it's over or without dates.
 */
export function countdown(start: string | null, end: string | null, today: string): string | null {
  if (!start) return null;
  const until = dayNumber(start) - dayNumber(today);
  if (until > 1) return `${until} days to go`;
  if (until === 1) return "Tomorrow";
  if (dayNumber(end ?? start) >= dayNumber(today)) return "Happening now";
  return null;
}

/** "Day 3" for a date inside the trip; "" outside it or without trip dates. */
export function tripDayLabel(date: string, start: string | null, end: string | null): string {
  if (!start) return "";
  const n = dayNumber(date) - dayNumber(start) + 1;
  if (n < 1 || (end && dayNumber(date) > dayNumber(end))) return "";
  return `Day ${n}`;
}

/**
 * A Google Maps search for a name near a place (Google's "Maps URLs": no API key, no cost). Nobody has checked
 * that it finds the right place.
 */
export function mapsSearchUrl(name: string, near: string | null): string {
  const query = near && !name.includes(near) ? `${name}, ${near}` : name;
  return `https://www.google.com/maps/search/?api=1&${new URLSearchParams({ query })}`;
}

/** A Maps search for the stop's name near its location, or the trip's destination. */
export function mapsUrl(a: Activity, destination: string | null): string {
  return mapsSearchUrl(a.name, a.location || destination);
}

/**
 * "About $20 each", "Miami Beach Marina, about $20 each", or just the place: under a stop's name.
 * A place that's only the trip's destination ("Miami") is left out.
 */
export function stopDetails(a: Activity, currency: string, destination?: string | null): string {
  const cost = a.est_per_person_cents ? `about ${formatMoney(a.est_per_person_cents, currency)} each` : "";
  const place = a.location && a.location.trim().toLowerCase() !== destination?.trim().toLowerCase() ? a.location : null;
  const text = [place, cost].filter(Boolean).join(", ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Same order and sort minutes as trip_model/activity.py SLOTS.
const SLOT_MINUTES: Record<Slot, number> = { morning: 540, lunch: 720, afternoon: 900, dinner: 1140, night: 1320 };
const SLOT_LABEL: Record<Slot, string> = {
  morning: "Morning", lunch: "Lunch", afternoon: "Afternoon", dinner: "Dinner", night: "Night",
};

/** "2pm" for a clock time, "Lunch" for a slot, or null when it's just on a day. */
export function whenLabel(a: Activity): string | null {
  return formatTime(a.start) ?? (a.slot ? SLOT_LABEL[a.slot] : null);
}

/** Minutes into the day for ordering: plans with just the day first, then slots and clock times together. */
function minutesInto(a: Activity): number {
  if (a.start && a.start.length > 10) {
    const [h, min] = a.start.slice(11, 16).split(":").map(Number);
    return h * 60 + min;
  }
  return a.slot ? SLOT_MINUTES[a.slot] : -1;
}

export function formatTime(iso: string | null): string | null {
  if (!iso || iso.length <= 10) return null;
  const [h, min] = iso.slice(11, 16).split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  const hour = h % 12 === 0 ? 12 : h % 12;
  return min ? `${hour}:${String(min).padStart(2, "0")}${suffix}` : `${hour}${suffix}`;
}

export type Day = { date: string | null; activities: Activity[] };

/** Activities grouped by calendar day, in order through the day (see minutesInto); undated ones last. */
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
    activities: days.get(date)!.sort((x, y) => minutesInto(x) - minutesInto(y)),
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

/** "5 days" for a trip's dates; null without both. */
export function tripLength(start: string | null, end: string | null): string | null {
  if (!start || !end) return null;
  const n = dayNumber(end) - dayNumber(start) + 1;
  return n === 1 ? "1 day" : `${n} days`;
}

const WEEKDAY_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/**
 * The trip's days with nothing on them: "Friday and Saturday are open." Weekday names for a trip
 * of a week or less, dates for longer ones. null when every day has something (or no dates).
 */
export function openDaysLine(activities: Activity[], start: string | null, end: string | null): string | null {
  if (!start || !end) return null;
  const busy = new Set(activities.filter((a) => a.start).map((a) => a.start!.slice(0, 10)));
  const first = dayNumber(start);
  const last = dayNumber(end);
  if (last < first || last - first > 30) return null;
  const open: string[] = [];
  for (let n = first; n <= last; n++) {
    const iso = new Date(n * 86_400_000).toISOString().slice(0, 10);
    if (!busy.has(iso)) open.push(last - first < 7 ? WEEKDAY_LONG[new Date(n * 86_400_000).getUTCDay()] : formatDate(iso));
  }
  if (open.length === 0 || open.length === last - first + 1) return null;
  return `${listNames(open)} ${open.length === 1 ? "is" : "are"} open.`;
}

/** "5m", "3h", "2d" for the last week; a date ("Mar 1") before that or for anything in the future. */
export function timeAgo(iso: string, now: number): string {
  const then = Date.parse(iso.length <= 16 ? `${iso}Z` : iso);
  const mins = Math.floor((now - then) / 60_000);
  if (Number.isNaN(mins) || mins < 0 || mins >= 7 * 24 * 60) return formatDate(iso);
  if (mins < 60) return `${Math.max(1, mins)}m`;
  if (mins < 24 * 60) return `${Math.floor(mins / 60)}h`;
  return `${Math.floor(mins / (24 * 60))}d`;
}
