import type { PublicTrip } from "@/lib/types";

/** Places the group wants to do but hasn't put on a day: dashed chips, plus how to add one. */
export function Ideas({ ideas }: { ideas: PublicTrip["ideas"] }) {
  return (
    <>
      <ul className="flex flex-wrap gap-2">
        {ideas.map((i) => (
          <li key={i.idea_id} className="rounded-full border-2 border-dashed border-outline px-3.5 py-2.5 text-sm font-semibold">
            {i.name}
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted">Put one on a day in the group chat: &ldquo;@tripbot add {ideas[0].name} Saturday&rdquo;.</p>
    </>
  );
}
