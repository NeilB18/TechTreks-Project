"use client";

import Link from "next/link";

import { LockIcon } from "@/components/Icons";

import { useMemberData } from "./MemberData";

/**
 * Trip | Money, under the photo. Trip is /t/<token>, Money is /t/<token>/money. In sample mode
 * the links keep ?as= and ?theme=, so the preview carries over. Money shows a lock to anyone who
 * can't see it.
 */
export function TabSwitch({ current, query }: { current: "trip" | "money"; query: string }) {
  const { state, pagePath } = useMemberData();
  const locked = state.step === "signed-out" || state.step === "not-linked";
  const tab = (id: "trip" | "money", href: string, label: string, icon?: boolean) => {
    const on = id === current;
    return (
      <Link
        href={`${href}${query}`}
        aria-current={on ? "page" : undefined}
        className={`flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-full text-[15px] no-underline ${
          on ? "bg-white font-bold text-ground" : "font-semibold text-soft"
        }`}
      >
        {icon && <LockIcon size={15} stroke={2} />}
        {label}
      </Link>
    );
  };
  return (
    <nav aria-label="Trip sections" className="relative mx-5 mt-2.5 flex gap-1 rounded-full bg-fill p-1">
      {tab("trip", pagePath, "Trip")}
      {tab("money", `${pagePath}/money`, "Money", locked && current !== "money")}
    </nav>
  );
}
