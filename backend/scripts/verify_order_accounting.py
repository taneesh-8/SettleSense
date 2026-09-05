"""
One-off verification: for seed 42, confirm every one of the 53 synthetic
orders is accounted for EXACTLY ONCE across confirmed matches + exceptions
(using Exception_.order_ids, the engine's source of truth for order
attribution) — no order silently dropped, no order double-counted.
"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.generator import generate
from engine.pipeline import reconcile

SEED = 42


def main():
    raw_orders, raw_settlements, raw_bank = generate(seed=SEED)
    all_order_ids = {o.order_id for o in raw_orders}
    total = len(all_order_ids)

    result = reconcile(raw_orders, raw_settlements, raw_bank)

    confirmed_order_ids = set()
    for m in result.confirmed:
        confirmed_order_ids.update(m.order_ids)
    confirmed_sum = sum(len(m.order_ids) for m in result.confirmed)

    exception_order_ids = set()
    per_exception_order_counts = Counter()  # order_id -> how many exceptions claim it
    category_counts = Counter()             # tag -> order count
    for e in result.exceptions:
        for oid in e.order_ids:
            exception_order_ids.add(oid)
            per_exception_order_counts[oid] += 1
            category_counts[e.tag or e.record_type] += 1

    union = confirmed_order_ids | exception_order_ids
    overlap = confirmed_order_ids & exception_order_ids
    missing = all_order_ids - union
    double_claimed = {oid for oid, n in per_exception_order_counts.items() if n > 1} | overlap

    print(f"Total raw orders:            {total}")
    print(f"Confirmed matches:           {len(result.confirmed)} groups, "
          f"sum(len(order_ids))={confirmed_sum}, distinct order_ids={len(confirmed_order_ids)}")
    print(f"Exceptions:                  {len(result.exceptions)} records, "
          f"covering {len(exception_order_ids)} distinct orders")
    print(f"Union (confirmed + exceptions): {len(union)} / {total}")
    print()

    print("--- Per-category order-count breakdown ---")
    print(f"  {'confirmed':30s} {len(confirmed_order_ids)}")
    for tag, count in sorted(category_counts.items()):
        print(f"  {tag:30s} {count}")
    breakdown_total = len(confirmed_order_ids) + sum(category_counts.values())
    print(f"  {'TOTAL':30s} {breakdown_total}")
    print()

    ok = True
    if missing:
        ok = False
        print(f"❌ ORPHANED/DROPPED ({len(missing)}): {sorted(missing)}")
    else:
        print("✅ No orders dropped — every order appears in confirmed or an exception.")

    if double_claimed:
        ok = False
        print(f"❌ DOUBLE-COUNTED ({len(double_claimed)}): {sorted(double_claimed)}")
    else:
        print("✅ No orders double-counted — confirmed and exceptions are disjoint, "
              "and no order is claimed by more than one exception.")

    if breakdown_total != total:
        ok = False
        print(f"❌ Breakdown total {breakdown_total} != {total}")

    print()
    if ok and breakdown_total == total:
        print(f"CLEAN: {total} total = {len(confirmed_order_ids)} confirmed + "
              f"{sum(category_counts.values())} exceptions. Zero orphaned. Zero double-counted.")
    else:
        print("FAILED — see discrepancies above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
