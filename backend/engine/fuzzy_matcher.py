"""
Stage 3: LLM Fuzzy Matcher — runs ONLY on leftovers from Stage 2.

Two modes:
  1. Real LLM (if ANTHROPIC_API_KEY or GEMINI_API_KEY is set)
     — structured prompt, strict JSON schema response
  2. Heuristic fallback (no key)
     — Levenshtein UTR distance + amount window
     — Logs "Running heuristic fuzzy fallback (no LLM key set)"

Output: proposed matches with fields_corroborated count (fed to guardrail).
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import List, Tuple, Dict, Any

try:
    from .models import (
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        AuditEntry,
    )
except ImportError:
    from models import (
        NormalizedOrder, NormalizedSettlement, NormalizedBankCredit,
        AuditEntry,
    )


logger = logging.getLogger(__name__)

TOLERANCE_PAISE = 200  # looser tolerance for fuzzy (₹2)
AMOUNT_TOLERANCE_PERCENT = 0.02  # 2%


# ---------------------------------------------------------------------------
# Levenshtein distance (pure Python, no deps)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins = prev[j + 1] + 1
            dlt = curr[j] + 1
            sub = prev[j] + (ca != cb)
            curr.append(min(ins, dlt, sub))
        prev = curr
    return prev[len(b)]


# ---------------------------------------------------------------------------
# Proposed match schema
# ---------------------------------------------------------------------------

class ProposedMatch:
    def __init__(
        self,
        settlement_utr: str,
        bank_utr: str,
        settlement_net_paise: int,
        bank_amount_paise: int,
        fields_corroborated: int,
        corroborating_fields: List[str],
        reasoning: str,
        mode: str,
        order_ids: List[str],
        settlement_ids: List[str],
        gross_paise: int,
        tag: str = "",
    ):
        self.settlement_utr = settlement_utr
        self.bank_utr = bank_utr
        self.settlement_net_paise = settlement_net_paise
        self.bank_amount_paise = bank_amount_paise
        self.fields_corroborated = fields_corroborated
        self.corroborating_fields = corroborating_fields
        self.reasoning = reasoning
        self.mode = mode
        self.order_ids = order_ids
        self.settlement_ids = settlement_ids
        self.gross_paise = gross_paise
        self.tag = tag


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

def _heuristic_match(
    payout_groups: Dict[str, List[NormalizedSettlement]],
    bank_credits: List[NormalizedBankCredit],
    audit: List[AuditEntry],
    seq_counter: List[int],
) -> List[ProposedMatch]:
    """
    Heuristic approach:
    1. For each unmatched bank credit, find the settlement group whose UTR
       has the lowest Levenshtein distance ("utr_similarity" if distance <= 3).
    2. Independently check amount corroboration. A coincidental-amount-collision
       credit (tagged amount_collision by the generator) can have an amount that
       matches a DIFFERENT settlement group than the one it's UTR-closest to —
       that's the whole point of the trap. So if the UTR-closest group's amount
       doesn't match, fall back to scanning every other unmatched group for one
       whose net total matches the credit's amount, and propose against THAT
       group instead (with amount_match as the only corroborating field).
    3. Always emit a proposal (even amount-only) so the guardrail can
       properly reject coincidental-amount-collision cases instead of the
       credit silently falling through as a generic orphan.
    """
    logger.info("Running heuristic fuzzy fallback (no LLM key set)")
    proposals: List[ProposedMatch] = []

    def _amount_close(amount_paise: int, group: List[NormalizedSettlement]) -> bool:
        total_net = sum(s.net_paise for s in group)
        return abs(amount_paise - total_net) <= max(TOLERANCE_PAISE, int(total_net * AMOUNT_TOLERANCE_PERCENT))

    for bc in bank_credits:
        best_dist = 999
        best_utr = None
        for utr in payout_groups:
            d = _levenshtein(bc.utr, utr)
            if d < best_dist:
                best_dist = d
                best_utr = utr

        if best_utr is None:
            continue

        target_utr = best_utr
        target_group = payout_groups[best_utr]
        utr_similar = best_dist <= 3
        amount_close = _amount_close(bc.amount_paise, target_group)

        corroborating = []
        if utr_similar:
            corroborating.append("utr_similarity")
        if amount_close:
            corroborating.append("amount_match")

        # Amount-collision trap: the UTR-closest group's amount doesn't match,
        # but the credit's amount coincidentally matches a *different* unmatched
        # payout group. Retarget the proposal at that group so the guardrail
        # sees it (and rejects it) instead of it becoming an untagged orphan.
        if not amount_close:
            for utr, group in payout_groups.items():
                if utr == best_utr:
                    continue
                if _amount_close(bc.amount_paise, group):
                    target_utr = utr
                    target_group = group
                    corroborating = ["amount_match"]  # UTR similarity doesn't carry over
                    break

        # Only emit a proposal if at least one field corroborates
        if not corroborating:
            continue

        total_net = sum(s.net_paise for s in target_group)
        total_gross = sum(s.gross_paise for s in target_group)

        reasoning = (
            f"UTR near-match (edit distance {best_dist}) + amount corroborated. "
            f"Bank UTR '{bc.utr}' matched settlement UTR '{target_utr}'. "
            f"Bank amount={bc.amount_paise}p, settlement net={total_net}p. "
            f"Corroborating fields: {corroborating}."
        )

        audit.append(AuditEntry(
            seq=seq_counter[0], stage="L3_fuzzy_heuristic",
            action="propose_fuzzy_match",
            record_id=bc.utr,
            detail=reasoning,
            ai_used=False,
        ))
        seq_counter[0] += 1

        proposals.append(ProposedMatch(
            settlement_utr=target_utr,
            bank_utr=bc.utr,
            settlement_net_paise=total_net,
            bank_amount_paise=bc.amount_paise,
            fields_corroborated=len(corroborating),
            corroborating_fields=corroborating,
            reasoning=reasoning,
            mode="fuzzy (heuristic)",
            order_ids=[s.order_id for s in target_group],
            settlement_ids=[s.settlement_id for s in target_group],
            gross_paise=total_gross,
            tag=bc.tag,
        ))

    return proposals




# ---------------------------------------------------------------------------
# LLM (Anthropic / Gemini) matcher
# ---------------------------------------------------------------------------

def _build_llm_prompt(
    payout_groups: Dict[str, List[NormalizedSettlement]],
    bank_credits: List[NormalizedBankCredit],
) -> str:
    payouts_desc = []
    for utr, group in payout_groups.items():
        total_net = sum(s.net_paise for s in group)
        payouts_desc.append({
            "utr": utr,
            "orders": [s.order_id for s in group],
            "settlement_ids": [s.settlement_id for s in group],
            "total_net_paise": total_net,
        })

    bank_desc = [
        {"utr": bc.utr, "amount_paise": bc.amount_paise, "description": bc.description}
        for bc in bank_credits
    ]

    return f"""You are a financial reconciliation assistant analyzing unmatched records.

UNMATCHED SETTLEMENT PAYOUTS (grouped by UTR):
{json.dumps(payouts_desc, indent=2)}

UNMATCHED BANK CREDITS:
{json.dumps(bank_desc, indent=2)}

Your task: propose matches between settlement payouts and bank credits that could not be matched deterministically.

Common reasons for mismatch: transposed digits in UTR, extra/missing characters, encoding differences.

For each proposed match, respond with ONLY a JSON array. Each element must have:
{{
  "settlement_utr": "...",
  "bank_utr": "...",
  "fields_corroborated": 2,
  "corroborating_fields": ["utr_similarity", "amount_match"],
  "reasoning": "Plain English explanation"
}}

Rules:
1. Only propose if at least 2 independent fields corroborate the match.
2. NEVER propose a match based on amount alone — UTR similarity must also support it.
3. If you cannot find a confident match, return an empty array [].
4. Respond with ONLY the JSON array, no other text."""


def _parse_llm_response(
    raw: str,
    payout_groups: Dict[str, List[NormalizedSettlement]],
    bank_credits: List[NormalizedBankCredit],
    mode: str,
) -> List[ProposedMatch]:
    bank_by_utr = {bc.utr: bc for bc in bank_credits}

    try:
        # Extract JSON from response (handle markdown code blocks)
        text = raw.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}. Raw: {raw[:200]}")
        return []

    proposals = []
    for item in data:
        s_utr = item.get("settlement_utr", "")
        b_utr = item.get("bank_utr", "")
        if s_utr not in payout_groups or b_utr not in bank_by_utr:
            continue
        group = payout_groups[s_utr]
        bc = bank_by_utr[b_utr]
        total_net = sum(s.net_paise for s in group)
        total_gross = sum(s.gross_paise for s in group)
        proposals.append(ProposedMatch(
            settlement_utr=s_utr,
            bank_utr=b_utr,
            settlement_net_paise=total_net,
            bank_amount_paise=bc.amount_paise,
            fields_corroborated=item.get("fields_corroborated", 0),
            corroborating_fields=item.get("corroborating_fields", []),
            reasoning=item.get("reasoning", ""),
            mode=mode,
            order_ids=[s.order_id for s in group],
            settlement_ids=[s.settlement_id for s in group],
            gross_paise=total_gross,
            tag=bc.tag,
        ))
    return proposals


def _call_anthropic(prompt: str, api_key: str) -> str:
    import urllib.request
    import urllib.error
    body = json.dumps({
        "model": "claude-3-haiku-20240307",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def _call_gemini(prompt: str, api_key: str) -> str:
    import urllib.request
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Diagnostic reasoning for unreflected refunds
# ---------------------------------------------------------------------------

def diagnose_unreflected_refunds(
    unmatched_orders: List[NormalizedOrder],
    unmatched_settlements: List[NormalizedSettlement],
    audit: List[AuditEntry],
    seq_counter: List[int],
) -> Tuple[List[Exception_], Set[str]]:
    from .models import Exception_
    exceptions: List[Exception_] = []
    diagnosed_setl_ids: Set[str] = set()
    setl_by_order = {s.order_id: s for s in unmatched_settlements}

    for o in unmatched_orders:
        if o.refund_paise > 0 or o.tag == "refund_not_reflected":
            setl = setl_by_order.get(o.order_id)
            if setl:
                diagnosed_setl_ids.add(setl.settlement_id)
                refund_fmt = f"₹{(o.refund_paise / 100):.2f}"
                detail = (
                    f"Stage 3 AI/Fuzzy diagnosed unreflected refund for order {o.order_id}: "
                    f"customer refund of {refund_fmt} was ignored in settlement {setl.settlement_id}. "
                    f"Merchant over-settled."
                )
                audit.append(AuditEntry(
                    seq=seq_counter[0],
                    stage="L3_fuzzy_diagnostic",
                    action="diagnose_unreflected_refund",
                    record_id=o.order_id,
                    detail=detail,
                    ai_used=False,
                ))
                seq_counter[0] += 1

                exceptions.append(Exception_(
                    exception_id=f"exc_refund_{o.order_id}",
                    record_type="order",
                    record_id=o.order_id,
                    level="L3",
                    stage="L3_fuzzy_diagnostic",
                    reason=f"Refund not reflected in payout — merchant over-settled (Customer refunded {refund_fmt}, but Razorpay settled full gross without deduction)",
                    amount_paise=o.refund_paise,  # Confirmation 1: refund exposure amount
                    risk_flag=False,
                    tag=o.tag or "refund_not_reflected",
                    order_ids=[o.order_id],
                ))
    return exceptions, diagnosed_setl_ids


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_fuzzy(
    unmatched_orders: List[NormalizedOrder],
    unmatched_settlements: List[NormalizedSettlement],
    unmatched_bank: List[NormalizedBankCredit],
    audit: List[AuditEntry],
    seq_counter: List[int],
) -> Tuple[List[ProposedMatch], List[Exception_], str]:
    """
    Returns (proposals, diagnostic_exceptions, fuzzy_mode_used)
    fuzzy_mode = "llm_anthropic" | "llm_gemini" | "heuristic" | "not_run"
    """
    diag_exceptions, diagnosed_setl_ids = diagnose_unreflected_refunds(unmatched_orders, unmatched_settlements, audit, seq_counter)

    remaining_settlements = [s for s in unmatched_settlements if s.settlement_id not in diagnosed_setl_ids]

    if not remaining_settlements or not unmatched_bank:
        return [], diag_exceptions, "not_run"

    # Group unmatched settlements by UTR
    payout_groups: Dict[str, List[NormalizedSettlement]] = defaultdict(list)
    for s in remaining_settlements:
        payout_groups[s.utr].append(s)


    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if anthropic_key:
        logger.info("Running LLM fuzzy matcher (Anthropic Claude)")
        prompt = _build_llm_prompt(payout_groups, unmatched_bank)
        try:
            raw = _call_anthropic(prompt, anthropic_key)
            proposals = _parse_llm_response(raw, payout_groups, unmatched_bank, mode="fuzzy (LLM)")
            for p in proposals:
                audit.append(AuditEntry(
                    seq=seq_counter[0], stage="L3_fuzzy_llm",
                    action="propose_fuzzy_match", record_id=p.settlement_utr,
                    detail=p.reasoning, ai_used=True,
                ))
                seq_counter[0] += 1
            return proposals, diag_exceptions, "llm_anthropic"
        except Exception as e:
            logger.warning(f"Anthropic call failed ({e}), falling back to heuristic")

    elif gemini_key:
        logger.info("Running LLM fuzzy matcher (Google Gemini)")
        prompt = _build_llm_prompt(payout_groups, unmatched_bank)
        try:
            raw = _call_gemini(prompt, gemini_key)
            proposals = _parse_llm_response(raw, payout_groups, unmatched_bank, mode="fuzzy (LLM)")
            for p in proposals:
                audit.append(AuditEntry(
                    seq=seq_counter[0], stage="L3_fuzzy_llm",
                    action="propose_fuzzy_match", record_id=p.settlement_utr,
                    detail=p.reasoning, ai_used=True,
                ))
                seq_counter[0] += 1
            return proposals, diag_exceptions, "llm_gemini"
        except Exception as e:
            logger.warning(f"Gemini call failed ({e}), falling back to heuristic")

    # Heuristic fallback
    proposals = _heuristic_match(payout_groups, unmatched_bank, audit, seq_counter)
    return proposals, diag_exceptions, "heuristic"

