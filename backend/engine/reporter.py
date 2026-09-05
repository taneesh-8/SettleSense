"""
Stage 5: Reporter
Assembles the final ReconciliationReport from all stage outputs.
"""
from __future__ import annotations

from collections import Counter
from typing import List

try:
    from .models import (
        ConfirmedMatch, Exception_, AuditEntry,
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        ReconciliationReport, ReconciliationResult,
    )
except ImportError:
    from models import (
        ConfirmedMatch, Exception_, AuditEntry,
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        ReconciliationReport, ReconciliationResult,
    )



# ---------------------------------------------------------------------------
# Canonical reason-prefix -> expected tag, for exception categories with an
# unambiguous 1:1 mapping between what happened (reason) and why (tag).
# Guards against tag silently drifting from a stale/inherited ground-truth
# label instead of the exception's own category — e.g. a true orphan bank
# credit tagged with whatever seeded batch it originally came from
# ("refund_not_reflected", "duplicate_settlement") instead of "orphan_credit".
# ---------------------------------------------------------------------------
_CANONICAL_REASON_TAG = [
    ("Orphan bank credit", "orphan_credit"),
    ("Unsettled order", "unsettled"),
    ("Duplicate settlement", "duplicate_settlement"),
    ("Refund not reflected", "refund_not_reflected"),
]


def _validate_exception_tags(exceptions: List[Exception_]) -> None:
    """Assert every exception's tag is consistent with its own reason/stage —
    not with some other record's ground-truth label. Raises ValueError on
    the first mismatch found."""
    for e in exceptions:
        for prefix, expected_tag in _CANONICAL_REASON_TAG:
            if e.reason.startswith(prefix) and e.tag != expected_tag:
                raise ValueError(
                    f"Tag/reason mismatch on {e.exception_id}: reason starts with "
                    f"{prefix!r} but tag={e.tag!r} (expected {expected_tag!r}). "
                    f"An exception's tag must describe its own category, not an "
                    f"inherited/stale label from an unrelated record."
                )
        if (e.stage == "guardrail" and "amount-only match rejected" in e.reason
                and e.tag != "amount_collision"):
            raise ValueError(
                f"Tag/reason mismatch on {e.exception_id}: guardrail amount-only "
                f"rejection must be tagged 'amount_collision', got {e.tag!r}."
            )


def build_report(
    orders: List[NormalizedOrder],
    settlements: List[NormalizedSettlement],
    bank: List[NormalizedBankCredit],
    confirmed: List[ConfirmedMatch],
    exceptions: List[Exception_],
    audit: List[AuditEntry],
    fuzzy_mode: str,
) -> ReconciliationResult:
    # Count how many order records were touched by each stage
    stage_counts: Counter = Counter()
    for m in confirmed:
        stage_counts[m.stage] += len(m.order_ids)

    total_orders = len(orders)
    # Confirmation #2: confirmed_order_count is dynamically computed from confirmed matches array
    confirmed_order_count = sum(len(m.order_ids) for m in confirmed)

    # Match rate = dynamically computed confirmed order count / total orders
    match_rate = confirmed_order_count / total_orders if total_orders > 0 else 0.0

    # Rupees reconciled = sum of gross in confirmed matches
    paise_reconciled = sum(m.gross_paise for m in confirmed)

    # Rupees at risk = sum of amount_paise for risk-flagged exceptions (unsettled orders)
    paise_at_risk = sum(e.amount_paise for e in exceptions if e.risk_flag)

    # Correction #4: Total flagged exception money (sum of all exception amounts)
    paise_flagged_total = sum(e.amount_paise for e in exceptions)

    # Assert no money-bearing exception has amount_paise == 0
    for e in exceptions:
        if e.amount_paise <= 0:
            raise ValueError(f"Exception {e.exception_id} ({e.reason}) has invalid non-positive amount_paise: {e.amount_paise}")

    # Assert every exception's tag matches its own reason/category (catches
    # tag-classification bugs like an orphan credit inheriting its originating
    # batch's ground-truth tag instead of "orphan_credit")
    _validate_exception_tags(exceptions)

    # Sort audit log by seq
    sorted_audit = sorted(audit, key=lambda a: a.seq)

    report = ReconciliationReport(
        total_orders=total_orders,
        total_settlements=len(settlements),
        total_bank_credits=len(bank),
        confirmed_count=len(confirmed),
        confirmed_order_count=confirmed_order_count,
        exception_count=len(exceptions),
        match_rate=round(match_rate, 4),
        rupees_reconciled=round(paise_reconciled / 100, 2),
        rupees_at_risk=round(paise_at_risk / 100, 2),
        rupees_flagged_total=round(paise_flagged_total / 100, 2),
        paise_reconciled=paise_reconciled,
        paise_at_risk=paise_at_risk,
        paise_flagged_total=paise_flagged_total,
        stage_counts=dict(stage_counts),
        fuzzy_mode=fuzzy_mode,
    )


    return ReconciliationResult(
        report=report,
        confirmed=confirmed,
        exceptions=exceptions,
        audit_log=sorted_audit,
        orders=orders,
        settlements=settlements,
        bank=bank,
    )
