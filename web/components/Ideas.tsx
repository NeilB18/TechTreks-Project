import { listNames } from "@/lib/format";
import type { PublicTrip } from "@/lib/types";

/** Places the group wants to do but hasn't put on a day, plus how to add one. */
export function Ideas({ ideas }: { ideas: PublicTrip["ideas"] }) {
  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <h3 className="text-[17px] font-bold">Ideas, no day yet</h3>
      <p className="leading-normal">{listNames(ideas.map((i) => i.name))}</p>
      <p className="text-sm text-muted">Put one on a day in the group chat: &ldquo;@tripbot add {ideas[0].name} Saturday&rdquo;.</p>
    </div>
  );
}
