# split_proportional(amount_cents, weights) -> dict[person_id, int]
#     Whole-cent split in the ratio of `weights`. Used for percentage splits, refunds
#     (back in the ratio of the shares) and foreign-currency exact amounts.

from fractions import Fraction


def split_proportional(amount_cents: int, weights: dict) -> dict:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Weights must add up to more than zero.")
    exact = {person_id: Fraction(amount_cents) * weight / total for person_id, weight in weights.items()}
    shares = {person_id: int(share) for person_id, share in exact.items()}
    leftover = amount_cents - sum(shares.values())

    # Largest fractional remainder first; ties broken by stable ID order.
    by_remainder = sorted(sorted(exact), key=lambda person_id: exact[person_id] - shares[person_id],
                          reverse=True)
    for person_id in by_remainder[:leftover]:
        shares[person_id] += 1
    return shares
