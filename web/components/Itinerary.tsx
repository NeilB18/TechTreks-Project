import { formatDay, formatMoney, formatTime, groupByDay, isOutsideTrip } from "@/lib/format";
import type { Activity, TripInfo } from "@/lib/types";

export function Itinerary({ activities, trip }: { activities: Activity[]; trip: TripInfo }) {
  if (activities.length === 0) {
    return <p className="empty-state">No plans yet. Ask @tripbot for an itinerary in the group chat.</p>;
  }
  return (
    <ol className="space-y-6">
      {groupByDay(activities).map((day, index) => (
        <li key={day.date ?? "undated"}>
          <div className="day-label"><span className="day-number">{day.date ? `DAY ${index + 1}` : "SOON"}</span><h3 className="text-xs font-semibold">
            {day.date ? formatDay(day.date) : "Not scheduled yet"}
          </h3></div>
          <ul className="activity-list">
            {day.activities.map((a) => {
              const time = formatTime(a.start);
              const outside = isOutsideTrip(a, trip.start_date, trip.end_date);
              return (
                <li key={a.activity_id} className="activity-row flex flex-wrap items-start gap-x-3 gap-y-2">
                  <span className="w-11 shrink-0 pt-0.5 text-[10px] tabular-nums text-muted">{time ?? "Anytime"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold">
                      {a.name}
                      {a.important && <span className="ml-2 text-[9px] font-normal text-accent">★ Key plan</span>}
                    </p>
                    {a.location && <p className="mt-1 text-[10px] leading-relaxed text-muted">{a.location}</p>}
                    {outside && <p className="mt-1 text-xs font-medium text-warn">Outside the trip dates</p>}
                  </div>
                  {a.est_per_person_cents != null && a.est_per_person_cents > 0 && (
                    <span className="ml-auto shrink-0 rounded bg-[#edf1e5] px-2 py-1 text-[10px] tabular-nums">
                      ~{formatMoney(a.est_per_person_cents, trip.base_currency)}
                      <span className="text-muted"> / person</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}
