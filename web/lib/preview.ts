import type { LinkCode, MyTrip, TripPageData } from "./types";

// What the money section shows, and in sample mode (no backend) who the page is previewed as:
// the "Preview as" bar sets ?as= to "signed-out", "not-linked" or a member's id.
export type State =
  | { step: "loading" }
  | { step: "error"; message: string }
  | { step: "signed-out" }
  | { step: "not-linked"; code: LinkCode | null }
  | { step: "ready"; data: MyTrip };

/** Sample mode: who's looking. Default: the first person who owes someone, so the money shows. */
export function previewMember(sample: TripPageData | null): string {
  if (!sample) return "";
  const payer = sample.balances.suggested_payments[0]?.from;
  return payer ?? sample.detail.members.find((m) => m.active)?.id ?? "";
}

export function previewState(sample: TripPageData | null, as?: string): State {
  if (!sample) return { step: "error", message: "No money data here." };
  if (as === "signed-out") return { step: "signed-out" };
  if (as === "not-linked") return { step: "not-linked", code: null };
  const me = sample.detail.members.find((m) => m.id === as) ? as! : previewMember(sample);
  return { step: "ready", data: { ...sample, person_id: me, budget: sample.budgets?.[me] ?? null } };
}
