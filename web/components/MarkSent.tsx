"use client";

import { useRef, useState } from "react";

import { formatMoney } from "@/lib/format";
import { parseDollars, postJson } from "@/lib/post";

/**
 * "Mark as sent" for one of your payments: a pop-up from the bottom with the amount filled in
 * (partial is fine, up to what you owe). Saving records it and the bot posts "Mia sent Aarav $X."
 * in the group. In sample mode nothing is saved.
 */
export function MarkSent({
  tripId,
  to,
  who,
  owedCents,
  currency,
  preview,
  onSaved,
}: {
  tripId: string;
  to: string;
  who: string;
  owedCents: number;
  currency: string;
  preview: boolean;
  onSaved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One id per opening, so a double tap on "Yes, I sent it" records the payment once.
  const requestId = useRef("");

  const open = () => {
    setAmount((owedCents / 100).toFixed(2));
    setMessage(null);
    requestId.current = crypto.randomUUID();
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
    const cents = parseDollars(amount);
    if (!cents) return setMessage("Enter an amount, like 25 or 231.36.");
    if (cents > owedCents) return setMessage(`You owe ${who} ${formatMoney(owedCents, currency)}. Enter that or less.`);
    if (preview) return setMessage("Preview only: nothing was saved.");
    setBusy(true);
    try {
      await postJson(`/api/me/trips/${encodeURIComponent(tripId)}/payments`, {
        to, amount_cents: cents, request_id: requestId.current,
      });
      close();
      onSaved();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Couldn’t save it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={open} className="btn btn-outline flex-1">
        Mark as sent
      </button>
      <dialog
        ref={dialog}
        aria-labelledby={`sent-${to}`}
        className="mx-auto mt-auto mb-0 w-full max-w-2xl rounded-t-[28px] bg-paper p-5 pb-7 text-paper-ink backdrop:bg-black/50"
      >
        <h2 id={`sent-${to}`} className="display text-[28px]">Sent {who} the money?</h2>
        <label htmlFor={`amount-${to}`} className="mt-4 block text-sm font-bold">Amount you sent</label>
        <div className="mt-1.5 flex min-h-14 items-center gap-1 rounded-2xl border-2 border-paper-ink bg-white px-4">
          <span className="text-xl font-bold">$</span>
          <input
            id={`amount-${to}`}
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-xl font-bold tabular-nums outline-none"
          />
        </div>
        <p className="mt-1.5 text-sm text-paper-muted">Sent part of it? Change the amount.</p>
        <p className="mt-3 text-sm text-paper-muted">
          This updates everyone&rsquo;s balances, and @tripbot posts it in the group so {who} can check it arrived.
          No money moves through TechTreks.
        </p>
        {message && <p role="alert" className="mt-3 text-sm font-semibold text-paper-hot">{message}</p>}
        <div className="mt-4 flex flex-col gap-1">
          <button type="button" onClick={save} disabled={busy} className="btn btn-paper min-h-[52px] text-base disabled:opacity-60">
            Yes, I sent it
          </button>
          <button type="button" onClick={close} className="btn min-h-11 text-paper-ink">
            Not yet
          </button>
        </div>
      </dialog>
    </>
  );
}
