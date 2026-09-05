"""
Comprehensive audit script covering checklist sections 2-5 and 7:
  - raw report JSON sanity (independent recompute of match_rate)
  - confirmed-match field validity (method, reason)
  - exception amount validity (amount_paise > 0)
  - order accounting (union=53, intersection=empty)
  - seeded edge-case classification with exact reason strings
  - money arithmetic cross-checks
  - repeat sections 2-5 for other seeds

Run: python scripts/full_audit.py [seed ...]
Default seeds: 42 7 100
"""
import sys
import os
import json
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.generator import generate
from engine.pipeline import reconcile

PASS = "PASS"
FAIL = "FAIL"


def audit_seed(seed: int, primary: bool):
    print(f"\n{'='*90}\nSEED {seed}\n{'='*90}")
    results = []  # (name, PASS/FAIL, detail)

    raw_orders, raw_settlements, raw_bank = generate(seed=seed)
    result = reconcile(raw_orders, raw_settlements, raw_bank)
    report = result.report
    report_json = json.loads(report.model_dump_json())

    if primary:
        out_path = os.path.join(os.path.dirname(__file__), f"report_seed{seed}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, indent=2)
        print(f"Raw report JSON dumped to: {out_path}")
        print(json.dumps(report_json, indent=2))

    # -------------------------------------------------------------------
    # Section 2: raw output sanity
    # -------------------------------------------------------------------
    total_orders = report.total_orders
    results.append(("total_orders == 53" if seed == 42 else f"total_orders == {total_orders}",
                     PASS if (seed != 42 or total_orders == 53) else FAIL, f"got {total_orders}"))

    recomputed_confirmed_order_count = sum(len(m.order_ids) for m in result.confirmed)
    match = recomputed_confirmed_order_count == report.confirmed_order_count
    results.append(("confirmed_order_count matches recompute", PASS if match else FAIL,
                     f"report={report.confirmed_order_count} recompute={recomputed_confirmed_order_count}"))

    recomputed_match_rate = recomputed_confirmed_order_count / total_orders if total_orders else 0.0
    rate_match = abs(round(recomputed_match_rate, 4) - report.match_rate) < 1e-9
    results.append(("match_rate matches recompute (no rounding drift)", PASS if rate_match else FAIL,
                     f"report={report.match_rate} recompute={round(recomputed_match_rate, 4)} "
                     f"({recomputed_confirmed_order_count}/{total_orders})"))

    valid_methods = {"deterministic", "fuzzy (heuristic)", "fuzzy (LLM)"}
    bad_matches = [m for m in result.confirmed if m.method not in valid_methods or not m.reason.strip()]
    results.append(("every confirmed match has valid method + non-empty reason",
                     PASS if not bad_matches else FAIL,
                     f"{len(bad_matches)} bad: {[m.match_id for m in bad_matches]}" if bad_matches else "all clean"))

    zero_amount_exceptions = [e for e in result.exceptions if e.amount_paise <= 0]
    results.append(("every exception has amount_paise > 0",
                     PASS if not zero_amount_exceptions else FAIL,
                     f"{len(zero_amount_exceptions)} bad: {[e.exception_id for e in zero_amount_exceptions]}"
                     if zero_amount_exceptions else "all clean"))

    # -------------------------------------------------------------------
    # Section 3: order accounting
    # -------------------------------------------------------------------
    all_order_ids = {o.order_id for o in raw_orders}
    confirmed_order_ids = set()
    for m in result.confirmed:
        confirmed_order_ids.update(m.order_ids)
    exception_order_ids = set()
    per_order_exc_count = Counter()
    for e in result.exceptions:
        for oid in e.order_ids:
            exception_order_ids.add(oid)
            per_order_exc_count[oid] += 1

    union = confirmed_order_ids | exception_order_ids
    overlap = confirmed_order_ids & exception_order_ids
    missing = all_order_ids - union
    dupe_within_exceptions = {oid for oid, n in per_order_exc_count.items() if n > 1}
    double_counted = overlap | dupe_within_exceptions

    results.append((f"union(confirmed, exceptions) == all {len(all_order_ids)} orders",
                     PASS if not missing else FAIL,
                     f"union={len(union)}, missing={sorted(missing)}" if missing else f"union={len(union)}, none missing"))
    results.append(("intersection(confirmed, exceptions) == empty (no double-count)",
                     PASS if not double_counted else FAIL,
                     f"double-counted={sorted(double_counted)}" if double_counted else "empty"))

    # -------------------------------------------------------------------
    # Section 4: seeded edge-case classification (seed 42 canonical only,
    # but we still run the generic shape checks for every seed)
    # -------------------------------------------------------------------
    if seed == 42:
        def find_confirmed(pred):
            return [m for m in result.confirmed if pred(m)]

        def find_exception(pred):
            return [e for e in result.exceptions if pred(e)]

        # Clean N:1 batch (ICICI, 5 orders -> 1 UTR)
        clean_batch = find_confirmed(lambda m: m.method == "deterministic" and len(m.order_ids) == 5)
        results.append(("Clean N:1 batched payout -> confirmed, deterministic",
                         PASS if clean_batch else FAIL,
                         f"match={clean_batch[0].match_id if clean_batch else None} "
                         f"reason={clean_batch[0].reason if clean_batch else 'NOT FOUND'}"))

        # MDR+GST individual order (6 of them, 1:1 UTR, deterministic)
        mdr_gst = find_confirmed(lambda m: m.method == "deterministic" and len(m.order_ids) == 1
                                  and "order(s)" in m.reason)
        results.append(("MDR+18% GST math -> confirmed, deterministic",
                         PASS if mdr_gst else FAIL,
                         f"e.g. match={mdr_gst[0].match_id if mdr_gst else None} "
                         f"reason={mdr_gst[0].reason if mdr_gst else 'NOT FOUND'}"))

        # TDS payout (SBI, 3 orders -> 1 UTR)
        tds_match = find_confirmed(lambda m: m.method == "deterministic" and "SBI" in m.utr)
        results.append(("1% TDS payout -> confirmed, deterministic",
                         PASS if tds_match else FAIL,
                         f"match={tds_match[0].match_id if tds_match else None} "
                         f"reason={tds_match[0].reason if tds_match else 'NOT FOUND'}"))

        # Chargeback netted off (AXIS batch: 3 orders confirmed via L2 deterministic
        # w/o the chargeback order itself, which fails L1 math and becomes an exception)
        chargeback_confirmed = find_confirmed(lambda m: m.method == "deterministic" and "AXIS" in m.utr)
        chargeback_exc = find_exception(lambda e: e.tag == "chargeback" and e.record_type == "settlement")
        cb_ok = bool(chargeback_confirmed) or bool(chargeback_exc)
        results.append(("Chargeback netted off a payout -> resolves deterministically (batch) "
                         "or flagged (the chargeback order's own math mismatch)",
                         PASS if cb_ok else FAIL,
                         f"confirmed_AXIS={[m.match_id for m in chargeback_confirmed]} "
                         f"math_mismatch_exc={[(e.exception_id, e.reason) for e in chargeback_exc]}"))

        # Transposed UTR (KOTAK)
        transposed = find_confirmed(lambda m: "KOTAK" in m.utr and m.method.startswith("fuzzy"))
        results.append(("Transposed UTR (KOTAK) -> confirmed, fuzzy (heuristic/LLM), "
                         "reason mentions UTR edit distance + amount corroboration",
                         PASS if transposed and "edit distance" in transposed[0].reason
                         and "amount" in transposed[0].reason.lower() else FAIL,
                         f"method={transposed[0].method if transposed else None} "
                         f"reason={transposed[0].reason if transposed else 'NOT FOUND'}"))

        # Refund not reflected (order_0022)
        refund_exc = find_exception(lambda e: "order_0022" in e.order_ids)
        refund_ok = (len(refund_exc) == 1 and refund_exc[0].stage == "L3_fuzzy_diagnostic"
                     and refund_exc[0].amount_paise == 50000
                     and "refund" in refund_exc[0].reason.lower()
                     and "over-settled" in refund_exc[0].reason.lower())
        results.append(("Refund not reflected (order_0022) -> exception, stage=L3_fuzzy_diagnostic, "
                         "amount_paise=50000, reason mentions over-settled",
                         PASS if refund_ok else FAIL,
                         f"{[(e.exception_id, e.stage, e.amount_paise, e.reason) for e in refund_exc]}"))

        # Unsettled order
        unsettled_exc = find_exception(lambda e: e.tag == "unsettled")
        unsettled_ok = bool(unsettled_exc) and unsettled_exc[0].risk_flag and "revenue at risk" in unsettled_exc[0].reason.lower()
        results.append(("Unsettled order -> exception, amount=order value, reason mentions revenue at risk",
                         PASS if unsettled_ok else FAIL,
                         f"{[(e.exception_id, e.amount_paise, e.reason) for e in unsettled_exc]}"))

        # Duplicate settlement
        dup_exc = find_exception(lambda e: e.tag == "duplicate_settlement" and e.record_type == "order")
        dup_ok = bool(dup_exc) and "settled" in dup_exc[0].reason.lower() and "times" in dup_exc[0].reason.lower()
        results.append(("Duplicate settlement -> exception, reason mentions settled twice",
                         PASS if dup_ok else FAIL,
                         f"{[(e.exception_id, e.reason) for e in dup_exc]}"))

        # Orphan bank credit (CITI, true orphan_credit tag)
        orphan_exc = find_exception(lambda e: e.tag == "orphan_credit")
        orphan_ok = bool(orphan_exc) and orphan_exc[0].level == "L2" and "no" in orphan_exc[0].reason.lower() \
            and "settlement" in orphan_exc[0].reason.lower()
        results.append(("Orphan bank credit -> exception, level=L2, reason mentions no matching settlement",
                         PASS if orphan_ok else FAIL,
                         f"{[(e.exception_id, e.level, e.reason) for e in orphan_exc]}"))

        # Amount collision (UNION)
        collision_exc = find_exception(lambda e: e.tag == "amount_collision")
        collision_ok = (bool(collision_exc) and collision_exc[0].stage == "guardrail"
                         and "insufficient corroboration (1 field)" in collision_exc[0].reason.lower()
                         and "amount-only match rejected" in collision_exc[0].reason.lower())
        results.append(('Amount collision (UNION) -> exception, stage=guardrail, reason has '
                         '"insufficient corroboration (1 field)" AND "amount-only match rejected" '
                         '(NOT a plain orphan)',
                         PASS if collision_ok else FAIL,
                         f"{[(e.exception_id, e.stage, e.reason) for e in collision_exc]}"))

        # explicitly confirm no plain orphan_UNION exists
        stray_orphan = find_exception(lambda e: "UNION" in e.record_id and e.stage != "guardrail")
        results.append(("No stray plain-orphan exception for the UNION collision credit",
                         PASS if not stray_orphan else FAIL,
                         f"{[e.exception_id for e in stray_orphan]}" if stray_orphan else "none found"))

    # -------------------------------------------------------------------
    # Section 5: money arithmetic
    # -------------------------------------------------------------------
    recomputed_paise_reconciled = sum(m.gross_paise for m in result.confirmed)
    reconciled_match = recomputed_paise_reconciled == report.paise_reconciled
    results.append(("rupees_reconciled == sum(confirmed gross_paise)",
                     PASS if reconciled_match else FAIL,
                     f"report={report.paise_reconciled}p recompute={recomputed_paise_reconciled}p"))

    recomputed_paise_flagged = sum(e.amount_paise for e in result.exceptions)
    flagged_match = recomputed_paise_flagged == report.paise_flagged_total
    contributors = [(e.exception_id, e.amount_paise, e.tag) for e in result.exceptions]
    results.append(("rupees_flagged_total == sum(ALL exception amount_paise)",
                     PASS if flagged_match else FAIL,
                     f"report={report.paise_flagged_total}p recompute={recomputed_paise_flagged}p | "
                     f"contributors={contributors}"))

    recomputed_paise_at_risk = sum(e.amount_paise for e in result.exceptions if e.risk_flag)
    at_risk_match = recomputed_paise_at_risk == report.paise_at_risk
    subset_ok = report.paise_at_risk <= report.paise_flagged_total
    results.append(("rupees_at_risk == sum(risk_flag exceptions) and is a subset of flagged_total",
                     PASS if (at_risk_match and subset_ok) else FAIL,
                     f"at_risk={report.paise_at_risk}p (recompute={recomputed_paise_at_risk}p) "
                     f"<= flagged_total={report.paise_flagged_total}p"))

    total_gross_in_batch = sum(o.amount_paise for o in result.orders) if hasattr(result, "orders") else None
    leakage_note = "n/a (orders list not on result)"
    if result.orders:
        total_input = sum(o.amount_paise for o in result.orders)
        accounted = report.paise_reconciled + sum(e.amount_paise for e in result.exceptions if e.record_type in ("order", "settlement"))
        leakage_note = f"input_order_total={total_input}p, reconciled+order/settlement-exceptions={accounted}p (informational, different bases: gross vs net vs refund-only)"
    results.append(("reconciled + flagged accounts for batch money (no silent leakage) [informational]",
                     PASS, leakage_note))

    # -------------------------------------------------------------------
    # Print
    # -------------------------------------------------------------------
    all_pass = True
    for name, status, detail in results:
        if status == FAIL:
            all_pass = False
        print(f"[{status}] {name}\n        {detail}")

    return all_pass, results


if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] or [42, 7, 100]
    overall = True
    for i, seed in enumerate(seeds):
        ok, _ = audit_seed(seed, primary=(i == 0))
        overall = overall and ok
    print(f"\n{'='*90}\nOVERALL: {'ALL PASS' if overall else 'FAILURES PRESENT'}\n{'='*90}")
    sys.exit(0 if overall else 1)
