import { ChevronIcon } from "@/components/Icons";
import { formatDay, groupByDay, isOutsideTrip, openDaysLine, stopDetails, tripDayLabel, whenLabel } from "@/lib/format";
import type { Activity, TripInfo } from "@/lib/types";

// Days shown open; later ones are folded (tap to open), so a long trip stays short on a phone.
const OPEN_DAYS = 2;

type TripBits = Pick<TripInfo, "start_date" | "end_date" | "base_currency" | "destination">;

/** The plan, day by day (design canvas: "Trip tab"). Days are rows between thin lines, not cards. */
export function Itinerary({ activities, trip }: { activities: Activity[]; trip: TripBits }) {
  if (activities.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        <h3 className="text-[17px] font-bold">Nothing planned yet</h3>
        <p className="text-[15px] leading-[1.45] text-muted">
          Tell @tripbot what you want to do, like &ldquo;beach day Saturday&rdquo; or &ldquo;boat tour Saturday 2pm, $60 each&rdquo;, and it shows up here.
        </p>
      </div>
    );
  }
  const open = openDaysLine(activities, trip.start_date, trip.end_date);
  return (
    <>
      <ol className="border-b border-line">
        {groupByDay(activities).map((day, i) => (
          <li key={day.date ?? "undated"}>
            <details open={i < OPEN_DAYS} className="group border-t border-line">
              {/* A summary holds one heading plus phrasing content, so the layout is a grid, not nested blocks. */}
              <summary className="grid min-h-[52px] cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 py-2.5 [&::-webkit-details-marker]:hidden">
                <h3 className="text-[17px] font-bold">{day.date ? formatDay(day.date) : "Not scheduled yet"}</h3>
                <span className="row-span-2 inline-flex items-center gap-2 text-sm text-muted">
                  {day.date ? tripDayLabel(day.date, trip.start_date, trip.end_date) : ""}
                  <ChevronIcon size={18} stroke={2} className="transition-transform group-open:rotate-180" />
                </span>
                <span className="truncate text-sm text-muted group-open:hidden">
                  {day.activities.map((a) => a.name).join(", ")}
                </span>
              </summary>
              <ul className="flex flex-col pb-2">
                {day.activities.map((a) => (
                  <Stop key={a.activity_id} a={a} trip={trip} />
                ))}
              </ul>
            </details>
          </li>
        ))}
      </ol>
      {open && <p className="mt-0.5 text-[15px] text-muted">{open}</p>}
    </>
  );
}

function Stop({ a, trip }: { a: Activity; trip: TripBits }) {
  const time = whenLabel(a); // "2pm", or a slot like "Lunch"
  const details = stopDetails(a, trip.base_currency, trip.destination);
  return (
    <li className="grid grid-cols-[72px_minmax(0,1fr)_44px] items-center gap-2.5 py-1.5">
      <span className="text-[15px] text-muted tabular-nums">{time ?? "Any time"}</span>
      <span className="flex flex-col gap-0.5">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{a.name}</span>
          {a.important && <span className="rounded-full bg-accent px-2 py-0.5 text-xs font-bold text-accent-ink">Must do</span>}
        </span>
        {details && <span className="text-sm text-muted">{details}</span>}
        {a.booking_url && (
          <a href={a.booking_url} className="self-start text-sm font-semibold underline" target="_blank" rel="noreferrer">
            Booking link
          </a>
        )}
        {isOutsideTrip(a, trip.start_date, trip.end_date) && (
          <span className="text-[13px] font-semibold text-warn">Outside the trip dates</span>
        )}
      </span>
    </li>
  );
}
