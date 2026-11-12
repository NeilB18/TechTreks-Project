import { formatDay, formatTime, groupByDay, isOutsideTrip, mapsUrl, stopDetails, tripDayLabel } from "@/lib/format";
import type { Activity, TripInfo } from "@/lib/types";

// Days shown open; later ones are folded (tap to open), so a long trip stays short on a phone.
const OPEN_DAYS = 2;

export function Itinerary({
  activities,
  trip,
}: {
  activities: Activity[];
  trip: Pick<TripInfo, "start_date" | "end_date" | "base_currency" | "destination">;
}) {
  if (activities.length === 0) {
    return (
      <div className="rounded-[22px] border-2 border-dashed border-outline p-5">
        <h3 className="text-lg font-bold">Nothing planned yet</h3>
        <p className="mt-1 text-sm text-muted">
          Ask in the group chat, like &ldquo;@tripbot plan Saturday&rdquo; or &ldquo;@tripbot add Wynwood Walls Friday&rdquo;.
        </p>
      </div>
    );
  }
  return (
    <ol className="flex flex-col gap-3.5">
      {groupByDay(activities).map((day, i) => (
        <li key={day.date ?? "undated"}>
          <details open={i < OPEN_DAYS} className="card group px-[18px]">
            {/* A summary holds one heading plus phrasing content, so the layout is a grid, not nested blocks. */}
            <summary className="grid min-h-16 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 py-4 [&::-webkit-details-marker]:hidden">
              <h3 className="text-lg font-bold">{day.date ? formatDay(day.date) : "Not scheduled yet"}</h3>
              <span className="label-caps row-span-2">{day.date ? tripDayLabel(day.date, trip.start_date, trip.end_date) : ""}</span>
              <span className="truncate text-sm text-muted group-open:hidden">
                {day.activities.map((a) => a.name).join(", ")}
              </span>
            </summary>
            <ul className="pb-1.5">
              {day.activities.map((a) => (
                <Stop key={a.activity_id} a={a} trip={trip} />
              ))}
            </ul>
          </details>
        </li>
      ))}
    </ol>
  );
}

function Stop({ a, trip }: { a: Activity; trip: Pick<TripInfo, "start_date" | "end_date" | "base_currency" | "destination"> }) {
  const time = formatTime(a.start);
  const details = stopDetails(a, trip.base_currency);
  return (
    <li className="flex items-center gap-3 border-t border-line py-3">
      <span className="w-14 shrink-0 text-sm font-semibold text-muted tabular-nums">{time ?? "Any time"}</span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2">
          <span className="font-bold">{a.name}</span>
          {a.important && <span className="rounded-full bg-pop px-2 py-0.5 text-xs font-bold text-ground">Must do</span>}
        </p>
        {details && <p className="text-sm text-muted">{details}</p>}
        {a.booking_url && (
          <a href={a.booking_url} className="text-sm font-semibold text-pop underline" target="_blank" rel="noreferrer">
            Booking link
          </a>
        )}
        {isOutsideTrip(a, trip.start_date, trip.end_date) && (
          <p className="mt-1 text-xs font-semibold text-warn">Outside the trip dates</p>
        )}
      </div>
      <a
        href={mapsUrl(a, trip.destination)}
        target="_blank"
        rel="noreferrer"
        aria-label={`${a.name} on Google Maps`}
        className="map-btn"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" />
          <circle cx="12" cy="9.5" r="2.5" />
        </svg>
      </a>
    </li>
  );
}
