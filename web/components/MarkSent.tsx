"use client";

import { useRef, useState } from "react";

import { Avatar } from "@/components/Avatars";
import { Sheet, useSheet } from "@/components/Sheet";
import { formatMoney } from "@/lib/format";
import { parseDollars, postJson } from "@/lib/post";

/**
 * "Mark as sent" for one of your payments: a bottom sheet with the amount filled in (partial is
 * fine, up to what you owe). Saving records it and the bot posts "Mia sent Aarav $X." in the
 * group. In sample mode nothing is saved.
 */
export function MarkSent({
  tripId,
  to,
  who,
  whoIndex = 0,
  owedCents,
  currency,
  preview,
  onSaved,
  className = "btn btn-line flex-1 px-3",
  me,
}: {
  tripId: string;
  to: string;
  who: string;
  whoIndex?: number; // their position on the trip, for their initial's colour
  owedCents: number;
  currency: string;
  preview: boolean;
  onSaved: () => void;
  className?: string;
  me?: string; // your name, for the line the bot posts
}) {
  const { ref: sheetRef, open: openSheet, close: closeSheet } = useSheet();
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One id per opening, so a double tap on "Yes, I sent it" records the payment once.
  const requestId = useRef("");
  const owed = formatMoney(owedCents, currency);

  const open = () => {
    setAmount((owedCents / 100).toFixed(2));
    setMessage(null);
    requestId.current = crypto.randomUUID();
    openSheet();
  };

  async function save() {
    const cents = parseDollars(amount);
    if (!cents) return setMessage("Enter an amount, like 25 or 231.36.");
    if (cents > owedCents) return setMessage(`You owe ${who} ${owed}. Enter that or less.`);
    if (preview) return setMessage("Preview only: nothing was saved.");
    setBusy(true);
    try {
      await postJson(`/api/me/trips/${encodeURIComponent(tripId)}/payments`, {
        to, amount_cents: cents, request_id: requestId.current,
      });
      closeSheet();
      onSaved();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Couldn’t save it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" onClick={open} className={className}>
        Mark as sent
      </button>
      <Sheet dialogRef={sheetRef} onClose={closeSheet} labelledBy={`sent-${to}`}>
        <div className="flex items-center gap-3">
          <Avatar name={who} index={whoIndex} />
          <span className="flex flex-col gap-px">
            <h2 id={`sent-${to}`} className="wide text-[22px]">Mark as sent</h2>
            <span className="text-[15px] text-muted">You owe {who} {owed}</span>
          </span>
        </div>
        <form
          className="flex flex-col gap-2.5"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <label htmlFor={`amount-${to}`} className="font-bold">Amount you sent</label>
          <span className="field">
            <span aria-hidden="true" className="text-lg text-muted">$</span>
            <input
              id={`amount-${to}`}
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="min-w-0 flex-1 bg-transparent text-lg tabular-nums outline-none"
            />
          </span>
          <p className="text-sm text-muted">Sent part of it? Change the amount.</p>
          {message && <p role="alert" className="text-sm font-semibold text-warn">{message}</p>}
          <button type="submit" disabled={busy} className="btn btn-white mt-2 min-h-[52px] disabled:opacity-60">
            Yes, I sent it
          </button>
          <button type="button" onClick={closeSheet} className="btn btn-line">Cancel</button>
        </form>
        <p className="text-[13px] leading-[1.45] text-muted">
          @tripbot posts it in the group: &ldquo;{me ?? "You"} sent {who} {owed}.&rdquo; Balances update for everyone.
        </p>
      </Sheet>
    </>
  );
}
