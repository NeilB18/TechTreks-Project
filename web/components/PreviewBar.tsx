import { previewMember } from "@/lib/preview";
import type { TripPageData } from "@/lib/types";

/**
 * Sample mode only (no backend): see the page as someone signed out, someone not on the trip,
 * or any member. It never shows on the real site, where TRIP_API_URL is set.
 */
export function PreviewBar({ sample, pagePath, as }: { sample: TripPageData; pagePath: string; as?: string }) {
  const current = as ?? previewMember(sample);
  const options: [string, string][] = [
    ["signed-out", "Signed out"],
    ["not-linked", "Not on this trip"],
    ...sample.detail.members.filter((m) => m.active).map((m): [string, string] => [m.id, m.name]),
  ];
  return (
    <nav aria-label="Preview as" className="border-b-2 border-dashed border-outline bg-surface px-5 py-2.5">
      <p className="text-xs font-bold text-muted">Sample data. Preview the page as:</p>
      <ul className="mt-1.5 flex gap-1.5 overflow-x-auto pb-1">
        {options.map(([value, label]) => (
          <li key={value} className="shrink-0">
            <a
              href={`${pagePath}?as=${value}`}
              aria-current={value === current ? "page" : undefined}
              className={`btn min-h-11 px-3.5 text-sm ${value === current ? "btn-pop" : "btn-outline"}`}
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
