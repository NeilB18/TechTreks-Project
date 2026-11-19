"use client";

import { useSyncExternalStore } from "react";

import { Avatar } from "@/components/Avatars";
import { formatMoney, timeAgo } from "@/lib/format";
import { latestItems } from "@/lib/latest";

import { useMemberData } from "./MemberData";

const noop = () => () => {};
const thisMinute = () => Math.floor(Date.now() / 60_000) * 60_000;

/**
 * "Latest" on the Trip tab: the 4 newest expenses, refunds and payments marked as sent. Money news
 * only, so only people on the trip see it; for anyone else it renders nothing.
 */
export function Latest() {
  const { state } = useMemberData();
  // "3h" depends on the clock, so it's only worked out in the browser (null on the server).
  const now = useSyncExternalStore(noop, thisMinute, () => null);
  if (state.step !== "ready") return null;

  const { detail } = state.data;
  const me = state.data.person_id;
  const money = (c: number) => formatMoney(c, detail.trip.base_currency);
  const index = (id: string) => Math.max(0, detail.members.findIndex((m) => m.id === id));
  const name = (id: string) => (id === me ? "You" : detail.members.find((m) => m.id === id)?.name ?? id);
  const items = latestItems(detail);

  return (
    <section aria-labelledby="latest" className="flex flex-col gap-1.5 px-5 pt-7.5">
      <h2 id="latest" className="wide mb-1 text-xl">Latest</h2>
      {items.length === 0 ? (
        <p className="text-[15px] leading-[1.45] text-muted">
          Nothing yet. Payments and expenses people tell @tripbot about show up here.
        </p>
      ) : (
        <ol className="flex flex-col">
          {items.map((it) => (
            <li key={it.key} className="flex items-start gap-3 py-2.5">
              <Avatar name={detail.members.find((m) => m.id === it.who)?.name ?? "?"} index={index(it.who)} size={32} />
              <span className="flex min-w-0 flex-1 flex-col gap-px pt-1.5">
                <span className="text-[15px] leading-[1.4]">
                  <b>{name(it.who)}</b>{" "}
                  {it.kind === "paid" && <>paid {money(it.cents)}</>}
                  {it.kind === "refund" && <>logged a {money(it.cents)} refund</>}
                  {it.kind === "sent" && <>marked {money(it.cents)} to {it.to ? (it.to === me ? "you" : name(it.to)) : "someone"} as sent</>}
                </span>
                {it.what && <span className="truncate text-sm text-muted">{it.what}</span>}
              </span>
              <span className="flex-none pt-[7px] text-[13px] text-muted">{now === null ? "" : timeAgo(it.at, now)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
