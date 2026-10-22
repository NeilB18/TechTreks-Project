// Private budgets are only ever shown to their owner. Until sign-in exists
// (google-signin branch), this panel just explains where to find yours.
export function BudgetPanel() {
  return (
    <div className="rounded-xl border border-dashed border-line p-4">
      <p className="font-medium">🔒 My budget</p>
      <p className="mt-1 text-sm text-muted">
        Your budget is private. Only you can see it. Sign-in is coming soon; until then, DM @tripbot to
        check what you have left.
      </p>
    </div>
  );
}
