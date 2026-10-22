import { CopyButton } from "@/components/CopyButton";
import { formatMoney, payLink } from "@/lib/format";
import type { Balances as BalancesData, Member } from "@/lib/types";

export function Balances({
  balances,
  members,
  tripName,
}: {
  balances: BalancesData;
  members: Member[];
  tripName: string;
}) {
  const name = (id: string) => members.find((m) => m.id === id)?.name ?? id;
  const debts = Object.entries(balances.balances).flatMap(([from, { owes }]) =>
    owes.map((d) => ({ from, ...d })),
  );
  if (debts.length === 0) {
    return <p className="text-sm text-muted">Everyone&rsquo;s settled up. 🎉</p>;
  }
  return (
    <ul className="divide-y divide-line rounded-xl border border-line bg-card">
      {debts.map((d) => {
        const link = payLink(d.handle, d.amount_cents, tripName);
        return (
          <li key={`${d.from}-${d.to}`} className="flex flex-wrap items-center justify-between gap-2 p-3">
            <p>
              <span className="font-medium">{name(d.from)}</span> owes{" "}
              <span className="font-medium">{name(d.to)}</span>{" "}
              <span className="font-semibold tabular-nums">{formatMoney(d.amount_cents, balances.currency)}</span>
            </p>
            {link?.kind === "venmo" && (
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-full bg-accent px-3 py-1.5 text-sm font-medium text-background hover:opacity-90"
              >
                {link.label}
              </a>
            )}
            {link?.kind === "other" && <CopyButton text={link.handle} label={link.label} />}
          </li>
        );
      })}
    </ul>
  );
}
