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
  const payments = balances.suggested_payments;
  if (payments.length === 0) {
    return <p className="empty-state">Everyone&rsquo;s settled up. Enjoy the trip!</p>;
  }
  return (
    <ul className="space-y-3">
      {payments.map((d) => {
        const link = payLink(d.handle, d.amount_cents, tripName);
        return (
          <li key={`${d.from}-${d.to}`} className="rounded-lg border border-line p-3.5">
            <p className="text-xs leading-6">
              <span className="font-medium">{name(d.from)}</span> pays{" "}
              <span className="font-medium">{name(d.to)}</span>{" "}
              <span className="font-semibold tabular-nums">{formatMoney(d.amount_cents, balances.currency)}</span>
            </p>
            {link?.kind === "venmo" && (
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex rounded-md bg-[#edf2e5] px-3 py-1.5 text-[10px] font-semibold text-accent hover:bg-[#e0e9d2]"
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
