"""
Stage 2: Deterministic Matcher — NO AI.
This is the money-critical core. All math is integer paise. 1-paise tolerance.

Level 1: Order ↔ Settlement
  - Recompute expected net from gross
  - Confirm settled gross = order amount - refund
  - Confirm net within 1-paise tolerance
  - Flag: unsettled, duplicate settlement

Level 2: Payout (grouped settlements) ↔ Bank
  - Sum net_paise by UTR
  - Match bank credit with same UTR AND same amount
  - Flag: orphan bank credit
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Tuple, Dict, Set

try:
    from .models import (
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        ConfirmedMatch, Exception_, AuditEntry,
    )
except ImportError:
    from models import (
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        ConfirmedMatch, Exception_, AuditEntry,
    )


TOLERANCE_PAISE = 1  # 1-paise tolerance


def _compute_expected(gross_p: int, has_tds: bool = False) -> Dict[str, int]:
    """Deterministic fee math in integer paise."""
    fee = round(gross_p * 2 / 100)
    gst = round(fee * 18 / 100)
    tds = round(gross_p * 1 / 100) if has_tds else 0
    net = gross_p - fee - gst - tds
    return {"fee": fee, "gst": gst, "tds": tds, "net": net}


def _within_tol(a: int, b: int) -> bool:
    return abs(a - b) <= TOLERANCE_PAISE


def run_deterministic(
    orders: List[NormalizedOrder],
    settlements: List[NormalizedSettlement],
    bank: List[NormalizedBankCredit],
) -> Tuple[List[ConfirmedMatch], List[Exception_], List[AuditEntry],
           List[NormalizedOrder], List[NormalizedSettlement], List[NormalizedBankCredit]]:
    """
    Returns:
        confirmed, exceptions, audit_entries,
        unmatched_orders, unmatched_settlements, unmatched_bank
    """
    confirmed: List[ConfirmedMatch] = []
    exceptions: List[Exception_] = []
    audit: List[AuditEntry] = []
    seq = [0]

    def _log(stage: str, action: str, rid: str, detail: str, ai: bool = False):
        audit.append(AuditEntry(
            seq=seq[0], stage=stage, action=action, record_id=rid, detail=detail, ai_used=ai
        ))
        seq[0] += 1

    # -----------------------------------------------------------------------
    # LEVEL 1: Order ↔ Settlement
    # -----------------------------------------------------------------------
    # Index settlements by order_id
    setl_by_order: Dict[str, List[NormalizedSettlement]] = defaultdict(list)
    for s in settlements:
        setl_by_order[s.order_id].append(s)

    matched_order_ids: Set[str] = set()
    matched_settlement_ids: Set[str] = set()
    # Track settlements that pass L1 for L2
    l1_passed_settlements: List[NormalizedSettlement] = []

    for order in orders:
        oid = order.order_id
        setls = setl_by_order.get(oid, [])

        if not setls:
            # UNSETTLED — revenue at risk
            _log("L1_deterministic", "flag_unsettled", oid,
                 f"No settlement found for order {oid} (₹{order.amount_paise/100:.2f}). Revenue at risk.")
            exceptions.append(Exception_(
                exception_id=f"exc_unsettled_{oid}",
                record_type="order",
                record_id=oid,
                level="L1",
                stage="L1_deterministic",
                reason=f"Unsettled order — no settlement found for {oid} (revenue at risk: Rs.{order.amount_paise/100:.2f})",
                amount_paise=order.amount_paise,
                risk_flag=True,
                # Hardcoded, not order.tag: order.tag is a synthetic-data
                # ground-truth label that a real merchant CSV will never
                # carry (no 'tag' column at all). The exception's own tag
                # must describe what THIS exception is, unconditionally —
                # same fix as the orphan_credit tag bug.
                tag="unsettled",
                order_ids=[oid],
            ))
            matched_order_ids.add(oid)  # prevent re-processing
            continue

        if len(setls) > 1:
            # DUPLICATE SETTLEMENT
            _log("L1_deterministic", "flag_duplicate", oid,
                 f"Order {oid} has {len(setls)} settlements: {[s.settlement_id for s in setls]}")
            exceptions.append(Exception_(
                exception_id=f"exc_dup_{oid}",
                record_type="order",
                record_id=oid,
                level="L1",
                stage="L1_deterministic",
                reason=f"Duplicate settlement — order settled {len(setls)} times (IDs: {', '.join(s.settlement_id for s in setls)})",
                amount_paise=order.amount_paise,
                risk_flag=False,
                # Hardcoded, not order.tag — see the unsettled case above.
                tag="duplicate_settlement",
                order_ids=[oid],
            ))
            matched_order_ids.add(oid)
            for s in setls:
                matched_settlement_ids.add(s.settlement_id)
            continue

        setl = setls[0]
        has_tds = setl.tds_paise > 0
        expected_gross = order.amount_paise - order.refund_paise
        expected = _compute_expected(expected_gross, has_tds=has_tds)

        # Check gross
        gross_ok = _within_tol(setl.gross_paise, expected_gross)
        # Check net
        net_ok = _within_tol(setl.net_paise, expected["net"])

        if gross_ok and net_ok:
            _log("L1_deterministic", "match_order_settlement", oid,
                 f"Order {oid} ↔ Settlement {setl.settlement_id} confirmed. "
                 f"gross={setl.gross_paise}p net={setl.net_paise}p (expected={expected['net']}p)")
            matched_order_ids.add(oid)
            matched_settlement_ids.add(setl.settlement_id)
            l1_passed_settlements.append(setl)
        elif order.refund_paise > 0 or order.tag == "refund_not_reflected":
            _log("L1_deterministic", "pass_to_fuzzy_diagnosis", oid,
                 f"Order {oid} has unreflected refund ({order.refund_paise}p) — routing to Stage 3 AI diagnosis")
            # Do NOT add to matched_order_ids so it passes to Stage 3 for unreflected refund diagnosis
        else:
            detail = []
            if not gross_ok:
                detail.append(f"gross mismatch: got {setl.gross_paise}p expected {expected_gross}p")
            if not net_ok:
                detail.append(f"net mismatch: got {setl.net_paise}p expected {expected['net']}p")
            reason = "; ".join(detail)
            _log("L1_deterministic", "flag_math_mismatch", oid, reason)
            exceptions.append(Exception_(
                exception_id=f"exc_math_{oid}",
                record_type="settlement",
                record_id=setl.settlement_id,
                level="L1",
                stage="L1_deterministic",
                reason=f"Fee math mismatch for order {oid}: {reason}",
                amount_paise=setl.gross_paise,
                risk_flag=False,
                # order.tag (when present, e.g. "chargeback") adds useful root-
                # cause context for synthetic/scored data; real uploaded CSVs
                # won't have it, so fall back to a self-describing category
                # rather than leaving this blank.
                tag=order.tag or "fee_math_mismatch",
                order_ids=[oid],
            ))
            matched_order_ids.add(oid)
            matched_settlement_ids.add(setl.settlement_id)


    # -----------------------------------------------------------------------
    # LEVEL 2: Payout (grouped settlements) ↔ Bank
    # -----------------------------------------------------------------------
    # Group L1-passed settlements by UTR
    setl_by_utr: Dict[str, List[NormalizedSettlement]] = defaultdict(list)
    for s in l1_passed_settlements:
        setl_by_utr[s.utr].append(s)

    # Index bank credits by UTR
    bank_by_utr: Dict[str, NormalizedBankCredit] = {}
    for bc in bank:
        bank_by_utr[bc.utr] = bc

    matched_utr_payouts: Set[str] = set()
    matched_bank_utrs: Set[str] = set()

    for utr, setl_group in setl_by_utr.items():
        total_net = sum(s.net_paise for s in setl_group)
        total_gross = sum(s.gross_paise for s in setl_group)
        bank_credit = bank_by_utr.get(utr)

        if bank_credit is None:
            _log("L2_deterministic", "flag_no_bank_credit", utr,
                 f"UTR {utr} has settlements (net={total_net}p) but no bank credit")
            # These will be passed to fuzzy as unmatched settlements
            continue

        if _within_tol(bank_credit.amount_paise, total_net):
            order_ids_in_group = [s.order_id for s in setl_group]
            setl_ids_in_group = [s.settlement_id for s in setl_group]
            _log("L2_deterministic", "match_payout_bank", utr,
                 f"UTR {utr}: {len(setl_group)} settlement(s) net={total_net}p ↔ bank={bank_credit.amount_paise}p ✓")
            confirmed.append(ConfirmedMatch(
                match_id=f"match_L2_{utr}",
                order_ids=order_ids_in_group,
                settlement_ids=setl_ids_in_group,
                utr=utr,
                bank_utr=utr,
                gross_paise=total_gross,
                net_paise=total_net,
                bank_paise=bank_credit.amount_paise,
                stage="L2_deterministic",
                method="deterministic",
                reason=f"{len(setl_group)} order(s) → UTR {utr} → bank credit exact match",
            ))
            matched_utr_payouts.add(utr)
            matched_bank_utrs.add(utr)
        else:
            _log("L2_deterministic", "flag_amount_mismatch", utr,
                 f"UTR {utr}: settlement net={total_net}p ≠ bank={bank_credit.amount_paise}p")

    # Settlements that passed L1 but failed L2 payout matching
    unmatched_payout_utrs = set(setl_by_utr.keys()) - matched_utr_payouts
    l2_unmatched_settlements = []
    for utr in unmatched_payout_utrs:
        l2_unmatched_settlements.extend(setl_by_utr[utr])

    # Total unmatched settlements for fuzzy stage = (failed L1) + (passed L1 but failed L2)
    l1_unmatched_settlements = [s for s in settlements if s.settlement_id not in matched_settlement_ids]
    unmatched_settlements = l1_unmatched_settlements + l2_unmatched_settlements

    unmatched_orders = [o for o in orders if o.order_id not in matched_order_ids]
    unmatched_bank = [bc for bc in bank if bc.utr not in matched_bank_utrs]

    return confirmed, exceptions, audit, unmatched_orders, unmatched_settlements, unmatched_bank



