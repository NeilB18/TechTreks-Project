"use client";

import { type FormEvent, useState } from "react";

import { parseDollars, postJson } from "@/lib/post";

/**
 * Set or change your own budget's total (category limits stay a chat thing). Saving posts
 * "Mia's budget is now $900." in the group. In sample mode nothing is saved. Used on both tabs.
 */
export function BudgetForm({
  tripId,
  currentCents,
  preview,
  onSaved,
  onCancel,
}: {
  tripId: string;
  currentCents: number | null;
  preview: boolean;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [amount, setAmount] = useState(currentCents ? String(currentCents / 100) : "");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    const cents = parseDollars(amount);
    if (!cents) return setMessage("Enter an amount, like 800.");
    if (preview) return setMessage("Preview only: nothing was saved.");
    setBusy(true);
    try {
      await postJson(`/api/me/trips/${encodeURIComponent(tripId)}/budget`, { total_cents: cents });
      onSaved();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Couldn’t save it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-3">
      <label htmlFor="budget-total" className="font-bold">Most I want to spend on this trip</label>
      <span className="field min-h-[50px]">
        <span aria-hidden="true" className="text-[17px] text-muted">$</span>
        <input
          id="budget-total"
          inputMode="decimal"
          placeholder="600"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-[17px] tabular-nums outline-none placeholder:text-muted"
        />
      </span>
      {message && <p role="alert" className="text-sm font-semibold text-warn">{message}</p>}
      <div className="flex gap-2.5">
        <button type="submit" disabled={busy} className="btn btn-white flex-1 disabled:opacity-60">Save</button>
        {onCancel && <button type="button" onClick={onCancel} className="btn btn-line flex-1">Cancel</button>}
      </div>
      <p className="text-[13px] leading-[1.45] text-muted">
        Everyone on the trip can see it, and @tripbot posts the new total in the group.
      </p>
    </form>
  );
}
