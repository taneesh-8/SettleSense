"""
Stage 1: Ingestion / Normalizer
- Standardizes field names and types
- Converts ALL monetary values to integer paise (×100, rounded)
- Parses dates to ISO strings
- Strips whitespace from IDs
"""
from __future__ import annotations
import re
from typing import List

try:
    from .models import (
        RawOrder, RawSettlement, RawBankCredit,
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
    )
except ImportError:
    from models import (
        RawOrder, RawSettlement, RawBankCredit,
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
    )



def _to_paise(value: float) -> int:
    """Convert an INR float to integer paise. Never use float arithmetic post-conversion."""
    return round(value * 100)


def _clean_id(s: str) -> str:
    return s.strip()


def normalize_orders(raw: List[RawOrder]) -> List[NormalizedOrder]:
    result = []
    for r in raw:
        result.append(NormalizedOrder(
            order_id=_clean_id(r.order_id),
            created_at=r.created_at,
            customer=r.customer,
            amount_paise=_to_paise(r.amount_inr),
            refund_paise=_to_paise(r.refund_inr),
            payment_method=r.payment_method,
            status=r.status,
            tag=r.tag,
        ))
    return result


def normalize_settlements(raw: List[RawSettlement]) -> List[NormalizedSettlement]:
    result = []
    for r in raw:
        result.append(NormalizedSettlement(
            settlement_id=_clean_id(r.settlement_id),
            order_id=_clean_id(r.order_id),
            utr=_clean_id(r.utr),
            settled_at=r.settled_at,
            gross_paise=_to_paise(r.gross_inr),
            fee_paise=_to_paise(r.fee_inr),
            gst_paise=_to_paise(r.gst_inr),
            tds_paise=_to_paise(r.tds_inr),
            net_paise=_to_paise(r.net_inr),
            tag=r.tag,
        ))
    return result


def normalize_bank(raw: List[RawBankCredit]) -> List[NormalizedBankCredit]:
    result = []
    for r in raw:
        result.append(NormalizedBankCredit(
            utr=_clean_id(r.utr),
            credited_at=r.credited_at,
            amount_paise=_to_paise(r.amount_inr),
            description=r.description,
            tag=r.tag,
        ))
    return result


def parse_csv_orders(rows: List[dict]) -> List[RawOrder]:
    """Parse CSV rows (dicts from csv.DictReader) into RawOrder."""
    result = []
    for row in rows:
        result.append(RawOrder(
            order_id=row.get("order_id", ""),
            created_at=row.get("created_at", ""),
            customer=row.get("customer", ""),
            amount_inr=float(re.sub(r"[^\d.]", "", row.get("amount_inr", "0") or "0")),
            payment_method=row.get("payment_method", ""),
            status=row.get("status", ""),
            refund_inr=float(re.sub(r"[^\d.]", "", row.get("refund_inr", "0") or "0")),
        ))
    return result


def parse_csv_settlements(rows: List[dict]) -> List[RawSettlement]:
    result = []
    for row in rows:
        result.append(RawSettlement(
            settlement_id=row.get("settlement_id", ""),
            order_id=row.get("order_id", ""),
            utr=row.get("utr", ""),
            settled_at=row.get("settled_at", ""),
            gross_inr=float(re.sub(r"[^\d.]", "", row.get("gross_inr", "0") or "0")),
            fee_inr=float(re.sub(r"[^\d.]", "", row.get("fee_inr", "0") or "0")),
            gst_inr=float(re.sub(r"[^\d.]", "", row.get("gst_inr", "0") or "0")),
            tds_inr=float(re.sub(r"[^\d.]", "", row.get("tds_inr", "0") or "0")),
            net_inr=float(re.sub(r"[^\d.]", "", row.get("net_inr", "0") or "0")),
        ))
    return result


def parse_csv_bank(rows: List[dict]) -> List[RawBankCredit]:
    result = []
    for row in rows:
        result.append(RawBankCredit(
            utr=row.get("utr", ""),
            credited_at=row.get("credited_at", ""),
            amount_inr=float(re.sub(r"[^\d.]", "", row.get("amount_inr", "0") or "0")),
            description=row.get("description", ""),
        ))
    return result


if __name__ == "__main__":
    print("Normalizer module loaded successfully.")
    demo_order = RawOrder(order_id="ORD-1001", created_at="2024-01-01T10:00:00Z", customer="Test Customer", amount_inr=100.50, payment_method="UPI", status="captured", refund_inr=0.0)
    norm = normalize_orders([demo_order])
    print(f"Normalized order: {norm[0]}")

