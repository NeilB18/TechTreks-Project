import type { Activity } from "./types";

// "Add to calendar": an .ics file made in the browser from the trip's dates and its planned stops.
// Calendar apps (Apple, Google, Outlook) all open it. Nothing is sent anywhere.

const pad = (n: number) => String(n).padStart(2, "0");

/** "2027-03-14" -> "20270314" (an all-day date). */
function day(iso: string): string {
  return iso.slice(0, 10).replaceAll("-", "");
}

function nextDay(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + 1));
  return `${t.getUTCFullYear()}${pad(t.getUTCMonth() + 1)}${pad(t.getUTCDate())}`;
}

/** "2027-03-15T10:00" -> "20270315T100000": local "floating" time, as the trip's own clock. */
function time(iso: string): string {
  return `${day(iso)}T${iso.slice(11, 13)}${iso.slice(14, 16)}00`;
}

// Commas, semicolons and backslashes need escaping in ICS text; newlines become \n.
function text(s: string): string {
  return s.replace(/[\\;,]/g, (c) => `\\${c}`).replace(/\r?\n/g, "\\n");
}

export function tripCalendar(trip: {
  id: string;
  name: string;
  destination: string | null;
  start_date: string;
  end_date: string | null;
  url: string;
  activities: Activity[];
}): string {
  const stamp = `${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`;
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//TravelBot//Trip//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:trip-${trip.id}@travelbot`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${day(trip.start_date)}`,
    `DTEND;VALUE=DATE:${nextDay(trip.end_date ?? trip.start_date)}`,
    `SUMMARY:${text(trip.name)}`,
    ...(trip.destination ? [`LOCATION:${text(trip.destination)}`] : []),
    `DESCRIPTION:${text(`The trip page: ${trip.url}`)}`,
    "END:VEVENT",
  ];
  for (const a of trip.activities) {
    if (!a.start) continue;
    const timed = a.start.length > 10;
    lines.push(
      "BEGIN:VEVENT",
      `UID:stop-${trip.id}-${a.activity_id}@travelbot`,
      `DTSTAMP:${stamp}`,
      timed ? `DTSTART:${time(a.start)}` : `DTSTART;VALUE=DATE:${day(a.start)}`,
      timed
        ? `DTEND:${a.end && a.end.length > 10 ? time(a.end) : time(a.start.slice(0, 11) + pad(Math.min(23, Number(a.start.slice(11, 13)) + 1)) + a.start.slice(13, 16))}`
        : `DTEND;VALUE=DATE:${nextDay(a.start)}`,
      `SUMMARY:${text(a.name)}`,
      ...(a.location ? [`LOCATION:${text(a.location)}`] : []),
      "END:VEVENT",
    );
  }
  lines.push("END:VCALENDAR");
  return lines.join("\r\n") + "\r\n";
}
