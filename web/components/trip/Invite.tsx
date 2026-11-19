"use client";

import { useSearchParams } from "next/navigation";

import { CopyButton } from "@/components/CopyButton";

import { useMemberData } from "./MemberData";

/**
 * Invite friends to the trip's group chat, with its GroupMe share link. Only for people on the trip,
 * and only for groups made with Add a trip (older groups don't have the link saved). Right after
 * Add a trip (/t/<token>?new=1) it's a highlighted card saying the group is ready.
 */
export function Invite() {
  const { state } = useMemberData();
  const fresh = useSearchParams().get("new") === "1";
  const url = state.step === "ready" ? state.data.group_join_url : null;
  if (!url) return null;
  return (
    <section
      aria-label="Invite friends"
      className={`mx-3.5 flex flex-col gap-3 ${fresh ? "card mt-3 border-accent p-[18px]" : "px-1.5 pt-1"}`}
    >
      {fresh && (
        <span className="flex flex-col gap-1">
          <span className="text-lg font-bold">Your group chat is ready</span>
          <span className="text-[15px] leading-[1.45] text-muted">
            @tripbot is in it and you&rsquo;re the trip&rsquo;s leader. Invite your friends: they&rsquo;re on the
            trip the first time they @tripbot.
          </span>
        </span>
      )}
      <span className="flex gap-2.5">
        <a href={url} target="_blank" rel="noreferrer" className={`btn ${fresh ? "btn-white" : "btn-line"} flex-1`}>
          Open the group chat
        </a>
        <CopyButton text={url} label="Copy invite link" className="btn btn-line flex-1" />
      </span>
    </section>
  );
}
