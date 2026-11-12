"use client";

import { type FormEvent, useState } from "react";

import { parseDollars, postJson } from "@/lib/post";

/**
 * Set or change your own budget's total (category limits stay a chat thing). Saving posts
 * "Mia's budget is now $900." in the group. In sample mode nothing is saved.
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
    <form onSubmit={save} className="mt-3 flex flex-col gap-2">
      <label htmlFor="budget-total" className="text-sm font-bold">Most I want to spend on this trip</label>
      <div className="flex gap-2">
        <div className="flex min-h-12 flex-1 items-center gap-1 rounded-2xl border-2 border-outline bg-ground px-3.5">
          <span className="font-bold">$</span>
          <input
            id="budget-total"
            inputMode="numeric"
            placeholder="600"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="min-w-0 flex-1 bg-transparent font-bold tabular-nums outline-none placeholder:text-muted"
          />
        </div>
        <button type="submit" disabled={busy} className="btn btn-pop disabled:opacity-60">Save</button>
      </div>
      <p className="text-sm text-muted">Everyone on the trip can see it, and @tripbot posts the new total in the group.</p>
      {message && <p role="alert" className="text-sm font-semibold text-warn">{message}</p>}
      {onCancel && (
        <button type="button" onClick={onCancel} className="btn min-h-11 self-start px-0 text-sm text-muted">Cancel</button>
      )}
    </form>
  );
}
