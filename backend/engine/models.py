"""
Pydantic models for SettleSense.
ALL monetary values are stored as integer PAISE (1 INR = 100 paise).
No floats ever cross the engine boundary.
"""
from __future__ import annotations
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Raw input shapes (what the API receives / CSVs parse to)
# ---------------------------------------------------------------------------

class RawOrder(BaseModel):
    order_id: str
    created_at: str
    customer: str
    amount_inr: float          # raw float from Razorpay export — normalizer converts
    payment_method: str
    status: str
    refund_inr: float = 0.0
    tag: str = ""              # ground-truth tag for scoring

    class Config:
        populate_by_name = True


class RawSettlement(BaseModel):
    settlement_id: str
    order_id: str
    utr: str
    settled_at: str
    gross_inr: float
    fee_inr: float
    gst_inr: float
    tds_inr: float = 0.0
    net_inr: float
    tag: str = ""

    class Config:
        populate_by_name = True


class RawBankCredit(BaseModel):
    utr: str
    credited_at: str
    amount_inr: float
    description: str = ""
    tag: str = ""

    class Config:
        populate_by_name = True


# ---------------------------------------------------------------------------
# Normalized shapes (all money in integer paise)
# ---------------------------------------------------------------------------

class NormalizedOrder(BaseModel):
    order_id: str
    created_at: str
    customer: str
    amount_paise: int
    refund_paise: int = 0
    payment_method: str
    status: str
    tag: str = ""


class NormalizedSettlement(BaseModel):
    settlement_id: str
    order_id: str
    utr: str
    settled_at: str
    gross_paise: int
    fee_paise: int
    gst_paise: int
    tds_paise: int = 0
    net_paise: int
    tag: str = ""


class NormalizedBankCredit(BaseModel):
    utr: str
    credited_at: str
    amount_paise: int
    description: str = ""
    tag: str = ""


# ---------------------------------------------------------------------------
# Engine output shapes
# ---------------------------------------------------------------------------

MatchStage = Literal["L1_deterministic", "L2_deterministic", "L3_fuzzy_llm", "L3_fuzzy_heuristic"]
ExceptionLevel = Literal["L1", "L2", "L3", "guardrail"]

class ConfirmedMatch(BaseModel):
    match_id: str
    order_ids: List[str]
    settlement_ids: List[str]
    utr: str
    bank_utr: str
    gross_paise: int
    net_paise: int
    bank_paise: int
    stage: MatchStage
    method: str
    reason: str


class Exception_(BaseModel):
    exception_id: str
    record_type: str          # "order", "settlement", "bank"
    record_id: str
    level: ExceptionLevel
    stage: str
    reason: str
    amount_paise: int
    risk_flag: bool = False   # True = revenue at risk
    tag: str = ""
    order_ids: List[str] = []  # every order this exception covers — required for
                                # full 53-order accounting; empty only for exceptions
                                # (e.g. true orphan bank credits) that own no order


class AuditEntry(BaseModel):
    seq: int
    stage: str
    action: str
    record_id: str
    detail: str
    ai_used: bool = False


class ReconciliationReport(BaseModel):
    total_orders: int
    total_settlements: int
    total_bank_credits: int
    confirmed_count: int
    confirmed_order_count: int
    exception_count: int
    match_rate: float                  # 0.0–1.0 (computed dynamically: confirmed_order_count / total_orders)
    rupees_reconciled: float           # human display only
    rupees_at_risk: float              # unsettled orders revenue at risk
    rupees_flagged_total: float        # sum of all exception amounts
    paise_reconciled: int
    paise_at_risk: int
    paise_flagged_total: int
    stage_counts: dict                 # stage → count
    fuzzy_mode: str                    # "llm" | "heuristic" | "not_run"



class ReconciliationResult(BaseModel):
    report: ReconciliationReport
    confirmed: List[ConfirmedMatch]
    exceptions: List[Exception_]
    audit_log: List[AuditEntry]
    orders: List[NormalizedOrder] = []
    settlements: List[NormalizedSettlement] = []
    bank: List[NormalizedBankCredit] = []
