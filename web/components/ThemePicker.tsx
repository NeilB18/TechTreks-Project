"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CheckIcon, PhotoIcon } from "@/components/Icons";
import { Sheet, useSheet } from "@/components/Sheet";
import { useMemberData } from "@/components/trip/MemberData";
import { postJson } from "@/lib/post";
import { THEMES } from "@/lib/themes";
import type { Theme } from "@/lib/types";

/**
 * "Change theme", on the trip's photo. Only people on the trip see it. A bottom sheet with our
 * theme photos; saving reloads the page in the new look. In sample mode it only changes ?theme=
 * (nothing is saved). Themes the bot can't save yet (pickable: false) aren't offered.
 */
export function ThemePicker({ theme }: { theme: Theme }) {
  const { state, tripId, preview, tabPath, previewAs } = useMemberData();
  const [picked, setPicked] = useState<Theme>(theme);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { ref: sheetRef, open: openSheet, close: closeSheet } = useSheet();
  const router = useRouter();

  if (state.step !== "ready") return null;

  const open = () => {
    setPicked(theme);
    setError(null);
    openSheet();
  };
  async function save() {
    if (preview) {
      const q = new URLSearchParams({ ...(previewAs ? { as: previewAs } : {}), theme: picked });
      closeSheet();
      router.push(`${tabPath}?${q}`, { scroll: false });
      return;
    }
    setBusy(true);
    try {
      await postJson(`/api/me/trips/${encodeURIComponent(tripId)}/theme`, { theme: picked });
      closeSheet();
      router.refresh(); // the server renders the page again in the new theme
    } catch {
      setError("Couldn’t change the theme. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="absolute right-3.5 bottom-1 z-10 inline-flex min-h-11 items-center gap-1.5 rounded-full bg-white/16 px-3 text-[13px] font-semibold"
      >
        <PhotoIcon size={16} />
        Change theme
      </button>
      <Sheet dialogRef={sheetRef} onClose={closeSheet} labelledBy="theme-title">
        <div className="flex flex-col gap-1">
          <h2 id="theme-title" className="wide text-[22px]">Trip theme</h2>
          <p className="text-sm leading-[1.45] text-muted">Everyone on the trip sees the change.</p>
        </div>
        <div role="radiogroup" aria-label="Themes" className="grid grid-cols-3 gap-x-2.5 gap-y-3.5">
          {THEMES.filter((t) => t.pickable || t.id === theme).map((t) => {
            const on = t.id === picked;
            return (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPicked(t.id)}
                className="flex flex-col gap-2 text-left"
              >
                <span className={`relative block h-[104px] w-full overflow-hidden rounded-[14px] ${on ? "outline-3 outline-offset-2 outline-white" : ""}`}>
                  <Image src={t.photo} alt="" fill sizes="130px" loading="eager" className="object-cover" />
                  {on && (
                    <span aria-hidden="true" className="absolute top-1.5 right-1.5 inline-flex size-6 items-center justify-center rounded-full bg-white text-ground">
                      <CheckIcon size={14} stroke={3} />
                    </span>
                  )}
                </span>
                <span className={`text-sm ${on ? "font-bold text-ink" : "font-semibold text-soft"}`}>{t.name}</span>
              </button>
            );
          })}
        </div>
        {error && <p role="alert" className="text-sm font-semibold text-warn">{error}</p>}
        <div className="mt-1 flex gap-2.5">
          <button type="button" onClick={save} disabled={busy} className="btn btn-white min-h-[50px] flex-1 disabled:opacity-60">
            Save
          </button>
          <button type="button" onClick={closeSheet} className="btn btn-line min-h-[50px] flex-1">Cancel</button>
        </div>
      </Sheet>
    </>
  );
}
