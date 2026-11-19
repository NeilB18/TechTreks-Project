"use client";

import { Money } from "@/components/Money";
import { useMemberData } from "@/components/trip/MemberData";
import { MembersOnly } from "@/components/trip/MembersOnly";

/**
 * The Money tab's body: settle-up, budgets and everything spent for people on the trip, or the
 * sign-in / not-on-this-trip card for everyone else. The data comes from MemberDataProvider.
 */
export function MoneySection() {
  const { state } = useMemberData();
  if (state.step === "ready") return <Money data={state.data} />;
  return <MembersOnly className="mx-3.5 mt-5.5" />;
}
