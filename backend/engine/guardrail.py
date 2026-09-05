"""
Stage 4: Verification / Guardrail

Rules:
  - Accept proposed match ONLY if fields_corroborated >= 2
  - REJECT amount-only matches (single field = amount)
  - Log rejections as honest exceptions: "amount-only match rejected by guardrail"

This stage prevents the coincidental-amount-collision trap.
"""
from __future__ import annotations

from typing import List, Tuple

try:
    from .models import ConfirmedMatch, Exception_, AuditEntry
    from .fuzzy_matcher import ProposedMatch
except ImportError:
    from models import ConfirmedMatch, Exception_, AuditEntry
    from fuzzy_matcher import ProposedMatch



def run_guardrail(
    proposals: List[ProposedMatch],
    fuzzy_mode: str,
    audit: List[AuditEntry],
    seq_counter: List[int],
) -> Tuple[List[ConfirmedMatch], List[Exception_]]:
    """
    Returns (newly_confirmed, newly_excepted)
    """
    confirmed: List[ConfirmedMatch] = []
    exceptions: List[Exception_] = []

    # A settlement group can be targeted by more than one competing proposal
    # (e.g. the real transposed-UTR credit AND a coincidental amount-collision
    # credit both proposing against the same payout). Only the winning
    # (accepted) proposal actually owns that group's orders. A rejected rival
    # targeting the same group must NOT also claim those order_ids on its
    # exception — that would double-count orders already confirmed elsewhere.
    accepted_settlement_utrs = {p.settlement_utr for p in proposals if p.fields_corroborated >= 2}

    for p in proposals:
        # order_ids to attach to a REJECTED proposal's exception: only when
        # this settlement group has no accepted rival, i.e. these orders are
        # genuinely unresolved and would otherwise vanish from order accounting.
        rejected_order_ids = [] if p.settlement_utr in accepted_settlement_utrs else p.order_ids
        is_amount_only = (
            p.fields_corroborated == 1
            and p.corroborating_fields == ["amount_match"]
        )
        has_enough_fields = p.fields_corroborated >= 2

        if is_amount_only:
            # GUARDRAIL REJECTION — insufficient corroboration (1 field: amount_match only)
            reason = (
                f"Insufficient corroboration (1 field): amount-only match rejected by guardrail — "
                f"bank UTR '{p.bank_utr}' amount matches settlement net "
                f"({p.bank_amount_paise}p) but no other field corroborates. "
                f"Minimum 2 required. Routing to human review."
            )
            audit.append(AuditEntry(
                seq=seq_counter[0], stage="guardrail",
                action="reject_amount_only",
                record_id=p.bank_utr,
                detail=reason,
                ai_used=False,
            ))
            seq_counter[0] += 1
            exceptions.append(Exception_(
                exception_id=f"exc_guardrail_{p.bank_utr}",
                record_type="bank",
                record_id=p.bank_utr,
                level="guardrail",
                stage="guardrail",
                reason=reason,
                amount_paise=p.bank_amount_paise,
                risk_flag=False,
                tag=p.tag or "amount_collision",
                order_ids=rejected_order_ids,
            ))

        elif has_enough_fields:
            # ACCEPTED
            stage_name = "L3_fuzzy_llm" if "llm" in fuzzy_mode else "L3_fuzzy_heuristic"
            reason = (
                f"Fuzzy match accepted by guardrail ({p.fields_corroborated} fields: "
                f"{', '.join(p.corroborating_fields)}). {p.reasoning}"
            )
            audit.append(AuditEntry(
                seq=seq_counter[0], stage="guardrail",
                action="accept_fuzzy_match",
                record_id=p.bank_utr,
                detail=reason,
                ai_used="llm" in fuzzy_mode,
            ))
            seq_counter[0] += 1
            confirmed.append(ConfirmedMatch(
                match_id=f"match_fuzzy_{p.bank_utr}",
                order_ids=p.order_ids,
                settlement_ids=p.settlement_ids,
                utr=p.settlement_utr,
                bank_utr=p.bank_utr,
                gross_paise=p.gross_paise,
                net_paise=p.settlement_net_paise,
                bank_paise=p.bank_amount_paise,
                stage=stage_name,  # type: ignore[arg-type]
                method=p.mode,
                reason=reason,
            ))

        else:
            # Not enough fields but not amount-only either
            reason = (
                f"Insufficient corroboration ({p.fields_corroborated} field(s): "
                f"{p.corroborating_fields}). Minimum 2 required. Routing to human review."
            )
            audit.append(AuditEntry(
                seq=seq_counter[0], stage="guardrail",
                action="reject_insufficient_fields",
                record_id=p.bank_utr,
                detail=reason,
                ai_used=False,
            ))
            seq_counter[0] += 1
            exceptions.append(Exception_(
                exception_id=f"exc_guardrail_insuf_{p.bank_utr}",
                record_type="bank",
                record_id=p.bank_utr,
                level="guardrail",
                stage="guardrail",
                reason=reason,
                amount_paise=p.bank_amount_paise,
                risk_flag=False,
                tag=p.tag,
                order_ids=rejected_order_ids,
            ))

    return confirmed, exceptions
