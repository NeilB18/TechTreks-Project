"use client";

import { CopyLinkButton } from "@/components/CopyLinkButton";
import { LinkIcon, MoneyIcon } from "@/components/Icons";
import { SignInButton } from "@/components/SignInButton";
import { formatMoney, payLink } from "@/lib/format";

import { useMemberData } from "./MemberData";

/**
 * The white bar floating at the bottom of the trip page: "Pay Aarav $400 | Copy link" when you
 * owe someone, "Sign in | Copy link" when signed out, otherwise just "Copy link". If you owe more
 * than one person (or the handle isn't Venmo), "Pay" goes to the Money tab's settle-up.
 */
const FIRST = "flex h-[46px] min-w-0 flex-[1.3] items-center justify-center gap-2 rounded-full px-1 font-bold text-ground no-underline";

export function FloatingBar({ moneyHref }: { moneyHref: string }) {
  const { state, signIn } = useMemberData();
  let first: { href: string; label: string; external: boolean } | null = null;
  const signedOut = state.step === "signed-out";

  // In sample mode, Sign in is a link that previews the page as a member.
  if (signedOut && signIn.previewHref) first = { href: signIn.previewHref, label: "Sign in", external: false };
  if (state.step === "ready") {
    const { detail, balances, person_id: me } = state.data;
    const youPay = balances.suggested_payments.filter((p) => p.from === me);
    const money = (c: number) => formatMoney(c, detail.trip.base_currency);
    if (youPay.length === 1) {
      const p = youPay[0];
      const who = detail.members.find((m) => m.id === p.to)?.name ?? p.to;
      const link = payLink(p.handle, p.amount_cents, detail.trip.name);
      first = link?.kind === "venmo"
        ? { href: link.href, label: `Pay ${who} ${money(p.amount_cents)}`, external: true }
        : { href: `${moneyHref}#settle-up`, label: `Pay ${who} ${money(p.amount_cents)}`, external: false };
    } else if (youPay.length > 1) {
      first = { href: `${moneyHref}#settle-up`, label: `Pay ${money(youPay.reduce((s, p) => s + p.amount_cents, 0))}`, external: false };
    }
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-30 px-5.5 pb-[max(16px,env(safe-area-inset-bottom))]">
      <div className="pointer-events-auto mx-auto flex h-[58px] max-w-md items-center rounded-full bg-white px-1.5 text-ground shadow-[0_10px_30px_rgb(0_0_0/0.35)]">
        {signedOut && !first && (
          <>
            <SignInButton next={signIn.next} className={`${FIRST} cursor-pointer`}>
              <span className="truncate">Sign in</span>
            </SignInButton>
            <span aria-hidden="true" className="h-[26px] w-px bg-[#d5d9e2]" />
          </>
        )}
        {first && (
          <>
            <a href={first.href} {...(first.external ? { target: "_blank", rel: "noreferrer" } : {})} className={FIRST}>
              {!signedOut && <MoneyIcon size={20} />}
              <span className="truncate">{first.label}</span>
            </a>
            <span aria-hidden="true" className="h-[26px] w-px bg-[#d5d9e2]" />
          </>
        )}
        <CopyLinkButton
          label={<><LinkIcon size={18} />Copy link</>}
          copiedLabel={<><LinkIcon size={18} />Copied</>}
          className="flex h-[46px] flex-1 items-center justify-center gap-2 rounded-full font-semibold text-ground"
        />
      </div>
    </div>
  );
}
