import { formatDay, formatMoney, formatTime, groupByDay, isOutsideTrip } from "@/lib/format";
import type { Activity, TripInfo } from "@/lib/types";

export function Itinerary({ activities, trip }: { activities: Activity[]; trip: TripInfo }) {
  if (activities.length === 0) {
    return <p className="text-sm text-muted">No plans yet. Ask @tripbot for an itinerary in the group chat.</p>;
  }
  return (
    <ol className="space-y-6">
      {groupByDay(activities).map((day) => (
        <li key={day.date ?? "undated"}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
            {day.date ? formatDay(day.date) : "Not scheduled yet"}
          </h3>
          <ul className="divide-y divide-line rounded-xl border border-line bg-card">
            {day.activities.map((a) => {
              const time = formatTime(a.start);
              const outside = isOutsideTrip(a, trip.start_date, trip.end_date);
              return (
                <li key={a.activity_id} className="flex items-start gap-3 p-3">
                  <span className="w-14 shrink-0 pt-0.5 text-sm tabular-nums text-muted">{time ?? "—"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {a.name}
                      {a.important && <span className="ml-2 text-xs text-accent">★ important</span>}
                    </p>
                    {a.location && <p className="truncate text-sm text-muted">{a.location}</p>}
                    {outside && <p className="mt-1 text-xs font-medium text-warn">Outside the trip dates</p>}
                  </div>
                  {a.est_per_person_cents != null && a.est_per_person_cents > 0 && (
                    <span className="shrink-0 text-sm tabular-nums">
                      ~{formatMoney(a.est_per_person_cents, trip.base_currency)}
                      <span className="text-muted">/person</span>
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
