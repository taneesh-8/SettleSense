"""
SettleSense reconciliation pipeline orchestrator.
Runs all 5 stages in sequence.
"""
from __future__ import annotations

from typing import List, Optional

try:
    from .models import (
        RawOrder, RawSettlement, RawBankCredit, ReconciliationResult, Exception_, AuditEntry,
    )
    from .normalizer import normalize_orders, normalize_settlements, normalize_bank
    from .deterministic import run_deterministic
    from .fuzzy_matcher import run_fuzzy
    from .guardrail import run_guardrail
    from .reporter import build_report
except ImportError:
    from models import (
        RawOrder, RawSettlement, RawBankCredit, ReconciliationResult, Exception_, AuditEntry,
    )
    from normalizer import normalize_orders, normalize_settlements, normalize_bank
    from deterministic import run_deterministic
    from fuzzy_matcher import run_fuzzy
    from guardrail import run_guardrail
    from reporter import build_report



def reconcile(
    raw_orders: List[RawOrder],
    raw_settlements: List[RawSettlement],
    raw_bank: List[RawBankCredit],
) -> ReconciliationResult:
    """Run the full 5-stage reconciliation pipeline."""

    # Stage 1: Normalize
    orders = normalize_orders(raw_orders)
    settlements = normalize_settlements(raw_settlements)
    bank = normalize_bank(raw_bank)

    # Stage 2: Deterministic
    det_confirmed, det_exceptions, det_audit, \
        unmatched_orders, unmatched_settlements, unmatched_bank = run_deterministic(
            orders, settlements, bank
        )

    seq_counter = [len(det_audit)]

    # Stage 3: Fuzzy
    proposals, diag_exceptions, fuzzy_mode = run_fuzzy(
        unmatched_orders, unmatched_settlements, unmatched_bank, det_audit, seq_counter
    )

    # Stage 4: Guardrail
    fuzzy_confirmed, fuzzy_exceptions = run_guardrail(
        proposals, fuzzy_mode, det_audit, seq_counter
    )


    # -----------------------------------------------------------------------
    # Post-guardrail: classify remaining unmatched bank credits
    # -----------------------------------------------------------------------
    # Collect all bank UTRs that got resolved (by either stage)
    resolved_bank_utrs = {m.bank_utr for m in det_confirmed} | {m.bank_utr for m in fuzzy_confirmed}
    guardrail_excepted_utrs = {e.record_id for e in fuzzy_exceptions}
    all_settlement_utrs = {s.utr for s in settlements}

    post_fuzzy_exceptions: List[Exception_] = []
    for bc in unmatched_bank:
        if bc.utr in resolved_bank_utrs or bc.utr in guardrail_excepted_utrs:
            continue
        # True orphan (fuzzy couldn't match it either)
        det_audit.append(AuditEntry(
            seq=seq_counter[0],
            stage="L2_deterministic",
            action="flag_orphan_credit",
            record_id=bc.utr,
            detail=f"Bank credit UTR {bc.utr} (₹{bc.amount_paise/100:.2f}) has no settlement match after all stages",
            ai_used=False,
        ))
        seq_counter[0] += 1
        post_fuzzy_exceptions.append(Exception_(
            exception_id=f"exc_orphan_{bc.utr}",
            record_type="bank",
            record_id=bc.utr,
            level="L2",
            stage="L2_deterministic",
            reason=f"Orphan bank credit — UTR {bc.utr} not matched by any settlement after all stages",
            amount_paise=bc.amount_paise,
            risk_flag=False,
            # Tag reflects what THIS exception is (an orphan bank credit),
            # not bc.tag — the seeded ground-truth label for whatever batch
            # originally generated this credit (e.g. "refund_not_reflected"
            # or "duplicate_settlement"). Reusing bc.tag here was the bug:
            # it made the tag describe the credit's origin story instead of
            # its actual failure category, and the two only coincide by luck
            # (e.g. for a genuine orphan_credit-tagged bank credit).
            tag="orphan_credit",
            # A true orphan bank credit owns no order: it either never had a
            # settlement (e.g. orphan_credit) or its original order was already
            # attributed to another exception (e.g. duplicate_settlement's
            # second credit, or a refund-diagnosed order's stray credit).
            order_ids=[],
        ))

    # Merge results
    all_confirmed = det_confirmed + fuzzy_confirmed
    all_exceptions = det_exceptions + diag_exceptions + fuzzy_exceptions + post_fuzzy_exceptions
    all_audit = det_audit  # mutated by fuzzy + guardrail stages


    # Stage 5: Report
    return build_report(
        orders=orders,
        settlements=settlements,
        bank=bank,
        confirmed=all_confirmed,
        exceptions=all_exceptions,
        audit=all_audit,
        fuzzy_mode=fuzzy_mode,
    )
