"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { THEMES } from "@/lib/themes";
import type { Me, Theme } from "@/lib/types";

function csrfToken(): string {
  return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] ?? "";
}

/**
 * "Change theme", next to Copy trip link. Only members of the trip see it: live, it asks /api/me/;
 * in sample mode, `preview` says whether the page is previewed as a member. Saving reloads the
 * page in the new look (sample mode only changes ?theme=, nothing is saved).
 */
export function ThemePicker({
  tripId,
  theme,
  preview,
}: {
  tripId: string;
  theme: Theme;
  // Sample mode: whether the page is previewed as a member, and where the preview lives.
  preview: { member: boolean; pagePath: string; as?: string } | null;
}) {
  const [member, setMember] = useState(preview?.member ?? false);
  const [picked, setPicked] = useState<Theme>(theme);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (preview) return;
    let cancelled = false;
    fetch("/api/me/", { cache: "no-store" })
      .then((r) => r.json() as Promise<Me>)
      .then((me) => !cancelled && setMember(me.signed_in && me.people.some((p) => p.trip_id === tripId)))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [preview, tripId]);

  if (!member) return null;

  const open = () => {
    setPicked(theme);
    setError(null);
    const d = dialog.current;
    if (d?.showModal) d.showModal();
    else d?.setAttribute("open", "");
  };
  const close = () => {
    const d = dialog.current;
    if (d?.close) d.close();
    else d?.removeAttribute("open");
  };
  async function save() {
    if (preview) {
      const q = new URLSearchParams({ ...(preview.as ? { as: preview.as } : {}), theme: picked });
      close();
      router.push(`${preview.pagePath}?${q}`, { scroll: false });
      return;
    }
    try {
      const res = await fetch(`/api/me/trips/${encodeURIComponent(tripId)}/theme`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ theme: picked }),
      });
      if (!res.ok) throw new Error(String(res.status));
      close();
      router.refresh(); // the server renders the page again in the new theme
    } catch {
      setError("Couldn’t change the theme. Try again.");
    }
  }

  const name = THEMES.find((t) => t.id === picked)?.name ?? "";
  return (
    <>
      <button type="button" onClick={open} className="btn btn-outline min-h-12">
        Change theme
      </button>
      <dialog
        ref={dialog}
        aria-labelledby="theme-title"
        className="mx-auto mt-auto mb-0 w-full max-w-2xl rounded-t-[28px] bg-paper p-5 pb-7 text-paper-ink backdrop:bg-black/50"
      >
        <h2 id="theme-title" className="display text-[28px]">Trip theme</h2>
        <p className="mt-1 text-sm text-paper-muted">Everyone on the trip sees the change.</p>
        <div role="radiogroup" aria-label="Themes" className="mt-4 grid grid-cols-3 gap-2.5">
          {THEMES.map((t) => (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={t.id === picked}
              onClick={() => setPicked(t.id)}
              className={`flex flex-col gap-2 rounded-[18px] border-[3px] p-1.5 text-left ${t.id === picked ? "border-paper-ink" : "border-transparent"}`}
            >
              <span data-theme={t.id} aria-hidden="true" className="relative block h-24 overflow-hidden rounded-[13px] bg-ground">
                <span className="absolute -right-3.5 -bottom-3.5 size-[70px] rounded-full bg-hot" />
                <span className="absolute bottom-3 left-2.5 h-2.5 w-10 rounded-full bg-pop" />
                <span className="display absolute top-2.5 left-2.5 text-base text-ink">Aa</span>
              </span>
              <span className="flex flex-col px-1 pb-1">
                <span className="text-sm font-bold">{t.name}</span>
                <span className="text-xs text-paper-muted">{t.note}</span>
              </span>
            </button>
          ))}
        </div>
        {error && <p role="alert" className="mt-3 text-sm font-semibold text-paper-hot">{error}</p>}
        <div className="mt-4 flex flex-col gap-1">
          <button type="button" onClick={save} className="btn btn-paper min-h-[52px] text-base">
            Use {name}
          </button>
          <button type="button" onClick={close} className="btn min-h-11 text-paper-ink">
            Cancel
          </button>
        </div>
      </dialog>
    </>
  );
}
