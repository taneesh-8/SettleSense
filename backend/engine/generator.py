"""
Synthetic data generator — Razorpay-shaped, 53 orders across 18 payouts.

Edge cases (with ground-truth tags):
  clean_batch          — 5 orders → 1 UTR credit, resolves deterministically
  mdr_gst              — standard MDR+GST, resolves deterministically
  tds_payout           — 1% TDS included, resolves deterministically
  chargeback           — chargeback netted off payout, resolves deterministically
  transposed_utr       — bank UTR has two digits swapped → fuzzy matcher
  refund_not_reflected — settlement ignores a refund → fuzzy matcher
  unsettled            — order never settled → exception (revenue at risk)
  duplicate_settlement — order settled twice → exception
  orphan_credit        — bank credit with no settlement → exception
  amount_collision     — amount matches 2 payouts, UTR matches neither → guardrail REJECTS
"""
from __future__ import annotations

import random
import hashlib
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

try:
    from .models import RawOrder, RawSettlement, RawBankCredit
except ImportError:
    from models import RawOrder, RawSettlement, RawBankCredit



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utr(prefix: str, n: int) -> str:
    """Generate a realistic-looking UTR."""
    return f"{prefix}{n:014d}"


def _settlement_fee(gross_inr: float, has_tds: bool = False) -> Tuple[float, float, float, float]:
    """Return (fee, gst, tds, net) in INR using the engine's formula."""
    gross_p = round(gross_inr * 100)
    fee_p = round(gross_p * 2 / 100)
    gst_p = round(fee_p * 18 / 100)
    tds_p = round(gross_p * 1 / 100) if has_tds else 0
    net_p = gross_p - fee_p - gst_p - tds_p
    return fee_p / 100, gst_p / 100, tds_p / 100, net_p / 100


def _ts(base: datetime, days: int = 0, hours: int = 0) -> str:
    return (base + timedelta(days=days, hours=hours)).isoformat()


def _oid(n: int) -> str:
    return f"order_{n:04d}"


def _sid(n: int) -> str:
    return f"setl_{n:04d}"


CUSTOMERS = [
    "Arjun Sharma", "Priya Patel", "Rahul Gupta", "Sneha Iyer", "Vikram Nair",
    "Anjali Singh", "Ravi Kumar", "Meera Reddy", "Amit Joshi", "Kavya Menon",
    "Suresh Pillai", "Divya Rao", "Nikhil Verma", "Pooja Bhat", "Kiran Desai",
]
METHODS = ["UPI", "card", "netbanking", "wallet"]


def generate(seed: int = 42) -> Tuple[List[RawOrder], List[RawSettlement], List[RawBankCredit]]:
    rng = random.Random(seed)
    base_dt = datetime(2024, 3, 1, 9, 0, 0)

    orders: List[RawOrder] = []
    settlements: List[RawSettlement] = []
    bank_credits: List[RawBankCredit] = []

    oid_counter = 1
    sid_counter = 1
    utr_counter = 1001

    # -----------------------------------------------------------------------
    # Batch 1: clean_batch — 5 orders → 1 UTR  (resolves deterministically)
    # -----------------------------------------------------------------------
    b1_utr = _utr("ICICI", utr_counter); utr_counter += 1
    b1_oids = []
    b1_gross_total = 0.0
    b1_net_total = 0.0
    for i in range(5):
        amt = rng.choice([500.0, 750.0, 1000.0, 1250.0, 1500.0])
        fee, gst, tds, net = _settlement_fee(amt)
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        b1_oids.append(oid)
        b1_gross_total += amt
        b1_net_total += net
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 0, i),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method=rng.choice(METHODS), status="paid", tag="clean_batch"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=b1_utr,
            settled_at=_ts(base_dt, 2, i),
            gross_inr=amt, fee_inr=fee, gst_inr=gst, tds_inr=0.0, net_inr=net,
            tag="clean_batch"
        ))
    bank_credits.append(RawBankCredit(
        utr=b1_utr, credited_at=_ts(base_dt, 2, 12),
        amount_inr=round(b1_net_total, 2),
        description="NEFT CREDIT BATCH 1", tag="clean_batch"
    ))

    # -----------------------------------------------------------------------
    # Batch 2: mdr_gst — 6 individual orders, standard MDR+GST
    # -----------------------------------------------------------------------
    for i in range(6):
        amt = rng.uniform(200, 2000)
        amt = round(amt, 2)
        fee, gst, tds, net = _settlement_fee(amt)
        utr = _utr("HDFC", utr_counter); utr_counter += 1
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 1, i),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method=rng.choice(METHODS), status="paid", tag="mdr_gst"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=utr,
            settled_at=_ts(base_dt, 3, i),
            gross_inr=amt, fee_inr=fee, gst_inr=gst, tds_inr=0.0, net_inr=net,
            tag="mdr_gst"
        ))
        bank_credits.append(RawBankCredit(
            utr=utr, credited_at=_ts(base_dt, 3, i + 2),
            amount_inr=round(net, 2),
            description=f"NEFT CREDIT ORDER {oid}", tag="mdr_gst"
        ))

    # -----------------------------------------------------------------------
    # Batch 3: tds_payout — 3 orders with TDS deducted
    # -----------------------------------------------------------------------
    b3_utr = _utr("SBI", utr_counter); utr_counter += 1
    b3_net_total = 0.0
    for i in range(3):
        amt = rng.choice([5000.0, 7500.0, 10000.0])
        fee, gst, tds, net = _settlement_fee(amt, has_tds=True)
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        b3_net_total += net
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 2, i),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method="netbanking", status="paid", tag="tds_payout"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=b3_utr,
            settled_at=_ts(base_dt, 4, i),
            gross_inr=amt, fee_inr=fee, gst_inr=gst, tds_inr=tds, net_inr=net,
            tag="tds_payout"
        ))
    bank_credits.append(RawBankCredit(
        utr=b3_utr, credited_at=_ts(base_dt, 4, 8),
        amount_inr=round(b3_net_total, 2),
        description="NEFT CREDIT TDS BATCH", tag="tds_payout"
    ))

    # -----------------------------------------------------------------------
    # Batch 4: chargeback — payout net reflects chargeback deduction
    # -----------------------------------------------------------------------
    b4_utr = _utr("AXIS", utr_counter); utr_counter += 1
    b4_net_total = 0.0
    for i in range(4):
        amt = rng.choice([1200.0, 1800.0, 2400.0, 3000.0])
        fee, gst, tds, net = _settlement_fee(amt)
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        cb_deduct = 0.0
        if i == 3:  # last order has chargeback netted off
            cb_deduct = amt * 0.5
            net -= cb_deduct
        b4_net_total += net
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 3, i),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method="card", status="paid",
            tag="chargeback" if i == 3 else "mdr_gst"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=b4_utr,
            settled_at=_ts(base_dt, 5, i),
            gross_inr=amt - cb_deduct, fee_inr=fee, gst_inr=gst, tds_inr=0.0,
            net_inr=round(net, 2),
            tag="chargeback" if i == 3 else "mdr_gst"
        ))
    bank_credits.append(RawBankCredit(
        utr=b4_utr, credited_at=_ts(base_dt, 5, 10),
        amount_inr=round(b4_net_total, 2),
        description="NEFT CREDIT CHARGEBACK BATCH", tag="chargeback"
    ))

    # -----------------------------------------------------------------------
    # Batch 5: transposed_utr — bank UTR has 2 digits transposed
    # -----------------------------------------------------------------------
    b5_utr = _utr("KOTAK", utr_counter); utr_counter += 1
    # Create a transposed version by swapping digit at position -3 and -1
    # e.g. KOTAK00000000001010 -> KOTAK00000000000110  (swap '1' at pos -4 and '0' at pos -3)
    # We craft a UTR where the last 4 digits are "1020" and transpose to "2010"
    b5_utr = b5_utr[:-4] + "1020"   # make last 4 distinct: 1020
    b5_utr_transposed = b5_utr[:-4] + "2010"  # transposed version
    b5_net_total = 0.0
    for i in range(3):
        amt = rng.choice([800.0, 1100.0, 1400.0])
        fee, gst, tds, net = _settlement_fee(amt)
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        b5_net_total += net
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 4, i),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method=rng.choice(METHODS), status="paid", tag="transposed_utr"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=b5_utr,
            settled_at=_ts(base_dt, 6, i),
            gross_inr=amt, fee_inr=fee, gst_inr=gst, tds_inr=0.0, net_inr=net,
            tag="transposed_utr"
        ))
    # Bank credit has the TRANSPOSED UTR
    bank_credits.append(RawBankCredit(
        utr=b5_utr_transposed, credited_at=_ts(base_dt, 6, 10),
        amount_inr=round(b5_net_total, 2),
        description="NEFT CREDIT KOTAK", tag="transposed_utr"
    ))

    # -----------------------------------------------------------------------
    # Batch 6: refund_not_reflected — settlement ignores a partial refund
    # -----------------------------------------------------------------------
    b6_utr = _utr("YES", utr_counter); utr_counter += 1
    amt6 = 2000.0
    refund_amt = 500.0  # refund issued but NOT in settlement
    fee6, gst6, _, net6 = _settlement_fee(amt6)  # settlement doesn't adjust for refund
    oid6 = _oid(oid_counter); oid_counter += 1
    sid6 = _sid(sid_counter); sid_counter += 1
    orders.append(RawOrder(
        order_id=oid6, created_at=_ts(base_dt, 5, 0),
        customer=rng.choice(CUSTOMERS), amount_inr=amt6,
        payment_method="UPI", status="partially_refunded",
        refund_inr=refund_amt, tag="refund_not_reflected"
    ))
    settlements.append(RawSettlement(
        settlement_id=sid6, order_id=oid6, utr=b6_utr,
        settled_at=_ts(base_dt, 7, 0),
        gross_inr=amt6, fee_inr=fee6, gst_inr=gst6, tds_inr=0.0, net_inr=net6,
        tag="refund_not_reflected"
    ))
    bank_credits.append(RawBankCredit(
        utr=b6_utr, credited_at=_ts(base_dt, 7, 4),
        amount_inr=round(net6, 2),  # bank paid full amount ignoring refund
        description="NEFT CREDIT YES BANK", tag="refund_not_reflected"
    ))

    # -----------------------------------------------------------------------
    # Edge: unsettled — order never settled (revenue at risk)
    # -----------------------------------------------------------------------
    oid_unsettled = _oid(oid_counter); oid_counter += 1
    orders.append(RawOrder(
        order_id=oid_unsettled, created_at=_ts(base_dt, 6, 0),
        customer=rng.choice(CUSTOMERS), amount_inr=999.0,
        payment_method="card", status="paid", tag="unsettled"
    ))
    # NO settlement, NO bank credit for this order

    # -----------------------------------------------------------------------
    # Edge: duplicate_settlement — same order settled twice
    # -----------------------------------------------------------------------
    oid_dup = _oid(oid_counter); oid_counter += 1
    amt_dup = 1500.0
    fee_d, gst_d, _, net_d = _settlement_fee(amt_dup)
    utr_dup1 = _utr("PNB", utr_counter); utr_counter += 1
    utr_dup2 = _utr("PNB", utr_counter); utr_counter += 1
    sid_d1 = _sid(sid_counter); sid_counter += 1
    sid_d2 = _sid(sid_counter); sid_counter += 1
    orders.append(RawOrder(
        order_id=oid_dup, created_at=_ts(base_dt, 7, 0),
        customer=rng.choice(CUSTOMERS), amount_inr=amt_dup,
        payment_method="UPI", status="paid", tag="duplicate_settlement"
    ))
    settlements.append(RawSettlement(
        settlement_id=sid_d1, order_id=oid_dup, utr=utr_dup1,
        settled_at=_ts(base_dt, 9, 0),
        gross_inr=amt_dup, fee_inr=fee_d, gst_inr=gst_d, tds_inr=0.0, net_inr=net_d,
        tag="duplicate_settlement"
    ))
    settlements.append(RawSettlement(
        settlement_id=sid_d2, order_id=oid_dup, utr=utr_dup2,
        settled_at=_ts(base_dt, 9, 4),
        gross_inr=amt_dup, fee_inr=fee_d, gst_inr=gst_d, tds_inr=0.0, net_inr=net_d,
        tag="duplicate_settlement"
    ))
    # Bank credits for both (both actually hit the bank — over-credit)
    bank_credits.append(RawBankCredit(
        utr=utr_dup1, credited_at=_ts(base_dt, 9, 8),
        amount_inr=round(net_d, 2), description="NEFT DUP 1", tag="duplicate_settlement"
    ))
    bank_credits.append(RawBankCredit(
        utr=utr_dup2, credited_at=_ts(base_dt, 9, 12),
        amount_inr=round(net_d, 2), description="NEFT DUP 2", tag="duplicate_settlement"
    ))

    # -----------------------------------------------------------------------
    # Edge: orphan_credit — bank credit with no settlement
    # -----------------------------------------------------------------------
    orphan_utr = _utr("CITI", utr_counter); utr_counter += 1
    bank_credits.append(RawBankCredit(
        utr=orphan_utr, credited_at=_ts(base_dt, 10, 0),
        amount_inr=4321.00, description="NEFT UNKNOWN", tag="orphan_credit"
    ))

    # -----------------------------------------------------------------------
    # Edge: amount_collision — amount matches an unmatched payout, UTR matches nothing
    # -----------------------------------------------------------------------
    # We use b5_net_total (KOTAK transposed-UTR batch) as the colliding amount.
    # KOTAK is unmatched after deterministic (its settlement UTR is KOTAK...1020 but
    # the bank credit UTR was transposed to KOTAK...2010). So the fuzzy engine sees
    # BOTH the KOTAK transposed credit AND this collision credit competing for the
    # same settlement group.
    # The collision UTR (UNION prefix) has Levenshtein distance ≥6 from KOTAK...1020,
    # so the heuristic finds NO utr_similarity — only amount_match (1 field).
    # Guardrail rejects it: "amount-only match (1 corroborating field)".
    collision_utr = _utr("UNION", utr_counter); utr_counter += 1
    bank_credits.append(RawBankCredit(
        utr=collision_utr, credited_at=_ts(base_dt, 11, 0),
        amount_inr=round(b5_net_total, 2),  # same net as KOTAK transposed-UTR payout
        description="NEFT AMOUNT COLLISION", tag="amount_collision"
    ))

    # -----------------------------------------------------------------------
    # Filler: more clean orders to reach ~53 total
    # -----------------------------------------------------------------------
    remaining = 53 - len(orders)
    for i in range(remaining):
        amt = round(rng.uniform(300, 3000), 2)
        fee, gst, tds, net = _settlement_fee(amt)
        utr = _utr("FILL", utr_counter); utr_counter += 1
        oid = _oid(oid_counter); oid_counter += 1
        sid = _sid(sid_counter); sid_counter += 1
        orders.append(RawOrder(
            order_id=oid, created_at=_ts(base_dt, 12 + i // 5, i % 5),
            customer=rng.choice(CUSTOMERS), amount_inr=amt,
            payment_method=rng.choice(METHODS), status="paid", tag="mdr_gst"
        ))
        settlements.append(RawSettlement(
            settlement_id=sid, order_id=oid, utr=utr,
            settled_at=_ts(base_dt, 14 + i // 5, i % 5),
            gross_inr=amt, fee_inr=fee, gst_inr=gst, tds_inr=0.0, net_inr=net,
            tag="mdr_gst"
        ))
        bank_credits.append(RawBankCredit(
            utr=utr, credited_at=_ts(base_dt, 14 + i // 5, i % 5 + 2),
            amount_inr=round(net, 2),
            description=f"NEFT FILL {i}", tag="mdr_gst"
        ))

    return orders, settlements, bank_credits
