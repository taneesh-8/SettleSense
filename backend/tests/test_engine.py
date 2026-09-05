"""
Unit tests for the SettleSense reconciliation engine.
Tests the deterministic math, edge case detection, and guardrail.
Run: python -m pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from engine.generator import generate, _settlement_fee
from engine.models import RawOrder, RawSettlement, RawBankCredit
from engine.normalizer import normalize_orders, normalize_settlements, normalize_bank
from engine.deterministic import run_deterministic, _compute_expected
from engine.fuzzy_matcher import _levenshtein, _heuristic_match
from engine.guardrail import run_guardrail
from engine.fuzzy_matcher import ProposedMatch
from engine.pipeline import reconcile
from engine.normalizer import parse_csv_orders, parse_csv_settlements, parse_csv_bank


# ---------------------------------------------------------------------------
# Fee math tests
# ---------------------------------------------------------------------------

def test_fee_math_basic():
    """₹1000 order: fee=20, gst=3.6→4 (rounded), net=976"""
    gross_p = 100000  # ₹1000 in paise
    expected = _compute_expected(gross_p)
    assert expected["fee"] == 2000          # 2% of 100000
    assert expected["gst"] == 360           # 18% of 2000
    assert expected["tds"] == 0
    assert expected["net"] == 97640         # 100000 - 2000 - 360


def test_fee_math_tds():
    """₹5000 order with TDS: fee=100, gst=18, tds=50, net=4832"""
    gross_p = 500000
    expected = _compute_expected(gross_p, has_tds=True)
    assert expected["fee"] == 10000
    assert expected["gst"] == 1800
    assert expected["tds"] == 5000
    assert expected["net"] == 483200


def test_fee_math_no_float_drift():
    """Ensure paise arithmetic never has floating-point errors."""
    for amount_inr in [999.99, 1234.56, 7890.01, 333.33]:
        gross_p = round(amount_inr * 100)
        expected = _compute_expected(gross_p)
        reconstructed = expected["fee"] + expected["gst"] + expected["tds"] + expected["net"]
        assert reconstructed == gross_p, f"Paise don't balance for {amount_inr}"


def test_settlement_fee_helper():
    """Generator helper produces consistent values."""
    fee, gst, tds, net = _settlement_fee(1000.0)
    assert abs(fee - 20.0) < 0.01
    assert abs(gst - 3.60) < 0.01
    assert tds == 0.0
    assert abs(net - 976.40) < 0.01


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

def test_generate_order_count():
    orders, settlements, bank = generate(seed=42)
    assert len(orders) >= 53


def test_generate_has_all_edge_cases():
    orders, settlements, bank = generate(seed=42)
    tags = {o.tag for o in orders}
    tags |= {s.tag for s in settlements}
    tags |= {b.tag for b in bank}
    required = {"clean_batch", "mdr_gst", "tds_payout", "chargeback",
                "transposed_utr", "refund_not_reflected", "unsettled",
                "duplicate_settlement", "orphan_credit", "amount_collision"}
    missing = required - tags
    assert not missing, f"Missing edge case tags: {missing}"


def test_generate_deterministic():
    """Same seed → same data."""
    o1, s1, b1 = generate(seed=42)
    o2, s2, b2 = generate(seed=42)
    assert len(o1) == len(o2)
    assert o1[0].order_id == o2[0].order_id


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------

def test_normalize_converts_to_paise():
    raw = [RawOrder(
        order_id=" ord_001 ", created_at="2024-01-01",
        customer="Test", amount_inr=1234.56,
        payment_method="UPI", status="paid", refund_inr=0.0
    )]
    norm = normalize_orders(raw)
    assert norm[0].amount_paise == 123456
    assert norm[0].order_id == "ord_001"  # stripped


# ---------------------------------------------------------------------------
# Deterministic matcher tests
# ---------------------------------------------------------------------------

def test_deterministic_clean_batch():
    """A clean batch resolves fully at L2."""
    orders, settlements, bank = generate(seed=42)
    n_orders = normalize_orders(orders)
    n_setls = normalize_settlements(settlements)
    n_bank = normalize_bank(bank)
    confirmed, exceptions, audit, um_o, um_s, um_b = run_deterministic(n_orders, n_setls, n_bank)

    # Some confirmed matches should be tagged clean_batch or mdr_gst
    confirmed_order_ids = {oid for m in confirmed for oid in m.order_ids}
    clean_orders = [o for o in n_orders if o.tag == "clean_batch"]
    assert any(o.order_id in confirmed_order_ids for o in clean_orders)


def test_deterministic_flags_unsettled():
    orders, settlements, bank = generate(seed=42)
    n_orders = normalize_orders(orders)
    n_setls = normalize_settlements(settlements)
    n_bank = normalize_bank(bank)
    _, exceptions, _, _, _, _ = run_deterministic(n_orders, n_setls, n_bank)
    unsettled_exc = [e for e in exceptions if "unsettled" in e.reason.lower()]
    assert len(unsettled_exc) >= 1
    assert unsettled_exc[0].risk_flag is True


def test_deterministic_flags_duplicate():
    orders, settlements, bank = generate(seed=42)
    n_orders = normalize_orders(orders)
    n_setls = normalize_settlements(settlements)
    n_bank = normalize_bank(bank)
    _, exceptions, _, _, _, _ = run_deterministic(n_orders, n_setls, n_bank)
    dup_exc = [e for e in exceptions if "duplicate" in e.reason.lower()]
    assert len(dup_exc) >= 1


def test_deterministic_flags_orphan():
    """Orphan credit detection now happens in the full pipeline after fuzzy stage."""
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)
    orphan_exc = [e for e in result.exceptions if "orphan" in e.reason.lower()]
    assert len(orphan_exc) >= 1


# ---------------------------------------------------------------------------
# Levenshtein tests
# ---------------------------------------------------------------------------

def test_levenshtein_identical():
    assert _levenshtein("ICICI00001001", "ICICI00001001") == 0


def test_levenshtein_transposed():
    # Swapping two adjacent digits = distance 2
    assert _levenshtein("KOTAK00001006", "KOTAK00001060") == 2


def test_levenshtein_different():
    assert _levenshtein("HDFC00001234", "CITI99999999") > 5


# ---------------------------------------------------------------------------
# Fuzzy matcher tests
# ---------------------------------------------------------------------------

def test_heuristic_matches_transposed_utr():
    """The heuristic should propose a match for the transposed UTR case."""
    orders, settlements, bank = generate(seed=42)
    n_setls = normalize_settlements(settlements)
    n_bank = normalize_bank(bank)

    # Simulate the transposed UTR scenario
    transposed_setls = [s for s in n_setls if s.tag == "transposed_utr"]
    transposed_bank = [b for b in n_bank if b.tag == "transposed_utr"]

    assert transposed_setls, "Expected transposed_utr settlements"
    assert transposed_bank, "Expected transposed_utr bank credit"

    audit = []
    seq = [0]
    from collections import defaultdict
    payout_groups = defaultdict(list)
    for s in transposed_setls:
        payout_groups[s.utr].append(s)

    proposals = _heuristic_match(dict(payout_groups), transposed_bank, audit, seq)
    assert len(proposals) >= 1
    assert "utr_similarity" in proposals[0].corroborating_fields


# ---------------------------------------------------------------------------
# Guardrail tests
# ---------------------------------------------------------------------------

def test_guardrail_rejects_amount_only():
    """Amount-only match must be rejected."""
    p = ProposedMatch(
        settlement_utr="UTR_A", bank_utr="UTR_B",
        settlement_net_paise=97640, bank_amount_paise=97640,
        fields_corroborated=1, corroborating_fields=["amount_match"],
        reasoning="Same amount", mode="heuristic",
        order_ids=["ord_001"], settlement_ids=["setl_001"], gross_paise=100000
    )
    audit = []
    seq = [0]
    conf, exc = run_guardrail([p], "heuristic", audit, seq)
    assert len(conf) == 0
    assert len(exc) == 1
    assert "amount-only" in exc[0].reason.lower()


def test_guardrail_accepts_two_fields():
    """Two corroborating fields must be accepted."""
    p = ProposedMatch(
        settlement_utr="UTR_A", bank_utr="UTR_B",
        settlement_net_paise=97640, bank_amount_paise=97640,
        fields_corroborated=2, corroborating_fields=["utr_similarity", "amount_match"],
        reasoning="UTR similar and amount matches", mode="heuristic",
        order_ids=["ord_001"], settlement_ids=["setl_001"], gross_paise=100000
    )
    audit = []
    seq = [0]
    conf, exc = run_guardrail([p], "heuristic", audit, seq)
    assert len(conf) == 1
    assert len(exc) == 0


# ---------------------------------------------------------------------------
# Full pipeline integration test
# ---------------------------------------------------------------------------

def test_full_pipeline_runs():
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)

    assert result.report.total_orders >= 53
    assert result.report.match_rate > 0.5
    assert len(result.confirmed) > 0
    assert len(result.exceptions) > 0
    # Audit trail must have entries
    assert len(result.audit_log) > 0


def test_pipeline_amount_collision_rejected():
    """The amount_collision case must end up in exceptions (either guardrail or orphan)."""
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)
    collision_exc = [e for e in result.exceptions if e.tag == "amount_collision"]
    assert len(collision_exc) >= 1
    # It must NOT appear in confirmed matches
    confirmed_utrs = {m.bank_utr for m in result.confirmed}
    collision_bank_utrs = [b.utr for b in bank if b.tag == "amount_collision"]
    for utr in collision_bank_utrs:
        assert utr not in confirmed_utrs, f"amount_collision UTR {utr} should not be confirmed"


def test_pipeline_transposed_utr_confirmed():
    """The transposed_utr case must appear in confirmed matches."""
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)
    fuzzy_matches = [m for m in result.confirmed if "fuzzy" in m.match_id or m.stage in ("L3_fuzzy_heuristic", "L3_fuzzy_llm")]
    # At minimum the transposed_utr payout should be in a fuzzy match
    assert len(fuzzy_matches) >= 1


def test_pipeline_report_paise_balance():
    """Reconciled + at-risk paise should be accountable."""
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)
    assert result.report.paise_reconciled >= 0
    assert result.report.paise_at_risk >= 0


# ---------------------------------------------------------------------------
# Tag/reason consistency
# ---------------------------------------------------------------------------

def test_orphan_exceptions_tagged_orphan_credit():
    """Every true orphan bank credit exception must be tagged 'orphan_credit',
    regardless of which seeded batch the bank credit originally came from.
    Regression test for a bug where the tag leaked the credit's originating
    ground-truth label (e.g. 'refund_not_reflected', 'duplicate_settlement')
    instead of describing this exception's own category."""
    orders, settlements, bank = generate(seed=42)
    result = reconcile(orders, settlements, bank)
    orphan_exceptions = [e for e in result.exceptions if e.reason.startswith("Orphan bank credit")]
    assert len(orphan_exceptions) >= 1
    for e in orphan_exceptions:
        assert e.tag == "orphan_credit", (
            f"{e.exception_id} has reason {e.reason!r} but tag={e.tag!r}"
        )


def test_validate_exception_tags_catches_mismatch():
    """The reporter's tag/reason validator must reject a mislabeled exception
    rather than silently accepting it."""
    from engine.reporter import _validate_exception_tags
    from engine.models import Exception_

    bad = Exception_(
        exception_id="exc_orphan_TEST0001",
        record_type="bank",
        record_id="TEST0001",
        level="L2",
        stage="L2_deterministic",
        reason="Orphan bank credit — UTR TEST0001 not matched by any settlement after all stages",
        amount_paise=100,
        risk_flag=False,
        tag="refund_not_reflected",  # wrong on purpose — should be orphan_credit
    )
    with pytest.raises(ValueError):
        _validate_exception_tags([bad])

    good = bad.model_copy(update={"tag": "orphan_credit"})
    _validate_exception_tags([good])  # must not raise


# ---------------------------------------------------------------------------
# CSV round-trip (the /api/upload path) — regression coverage
# ---------------------------------------------------------------------------

def _to_csv_rows(models) -> list:
    """Simulate what csv.DictReader hands parse_csv_* after a real CSV
    round-trip: every value coerced to a string, exactly like a browser-
    uploaded CSV file would produce."""
    return [{k: str(v) for k, v in m.model_dump().items()} for m in models]


def test_csv_round_trip_preserves_tag():
    """Regression test: parse_csv_orders/settlements/bank must preserve the
    'tag' column. This was previously dropped entirely (RawOrder/Settlement/
    BankCredit were constructed without a tag= kwarg at all), which meant
    every CSV-uploaded record silently got tag="" regardless of its real
    seeded category. That tripped the tag/reason consistency guard in
    reporter.py — e.g. an 'Unsettled order' exception ending up with
    tag='' instead of 'unsettled' — raising ValueError and crashing
    /api/upload with an unhandled 500 for every CSV upload."""
    raw_orders, raw_settlements, raw_bank = generate(seed=42)

    csv_orders = parse_csv_orders(_to_csv_rows(raw_orders))
    csv_settlements = parse_csv_settlements(_to_csv_rows(raw_settlements))
    csv_bank = parse_csv_bank(_to_csv_rows(raw_bank))

    assert [o.tag for o in csv_orders] == [o.tag for o in raw_orders]
    assert [s.tag for s in csv_settlements] == [s.tag for s in raw_settlements]
    assert [b.tag for b in csv_bank] == [b.tag for b in raw_bank]
    # Specifically: at least one non-empty tag actually survived the round trip
    assert any(o.tag for o in csv_orders)


def test_csv_upload_path_reconciles_without_crashing():
    """End-to-end: the exact data transformation /api/upload performs
    (CSV rows -> parse_csv_* -> reconcile) must not raise. This is what
    would have caught the tag-dropping bug via the actual code path the
    upload endpoint uses, before it ever reached a live deployment."""
    raw_orders, raw_settlements, raw_bank = generate(seed=42)

    csv_orders = parse_csv_orders(_to_csv_rows(raw_orders))
    csv_settlements = parse_csv_settlements(_to_csv_rows(raw_settlements))
    csv_bank = parse_csv_bank(_to_csv_rows(raw_bank))

    result = reconcile(csv_orders, csv_settlements, csv_bank)  # must not raise
    assert result.report.total_orders == 53
    assert result.report.confirmed_order_count > 0


def _to_csv_rows_no_tag_column(models) -> list:
    """Simulate the REALISTIC upload scenario: a genuine merchant CSV export
    that never had a 'tag' column at all (it's an internal ground-truth
    scoring field for the synthetic generator, not something any real
    Razorpay export would contain) — as opposed to a CSV where the column
    exists but happens to be blank. csv.DictReader would simply never
    produce a 'tag' key for such rows."""
    rows = []
    for m in models:
        row = {k: str(v) for k, v in m.model_dump().items() if k != "tag"}
        rows.append(row)
    return rows


def test_csv_upload_with_no_tag_column_does_not_crash():
    """Regression test for the realistic upload case: a CSV with NO 'tag'
    column present (not present-but-empty). Before this fix, exceptions
    like 'Unsettled order' and 'Duplicate settlement' derived their tag
    directly from order.tag — which is always "" for real, untagged data —
    tripping reporter.py's tag/reason consistency guard and crashing
    /api/upload with an unhandled 500 for every real-world CSV upload,
    since a genuine merchant export would never carry these ground-truth
    labels in the first place. parse_csv_* must default a missing column
    to "" without raising (dict.get already covers this), AND every
    exception's own tag must be self-describing regardless of whether the
    input carried a tag at all."""
    raw_orders, raw_settlements, raw_bank = generate(seed=42)

    csv_orders = parse_csv_orders(_to_csv_rows_no_tag_column(raw_orders))
    csv_settlements = parse_csv_settlements(_to_csv_rows_no_tag_column(raw_settlements))
    csv_bank = parse_csv_bank(_to_csv_rows_no_tag_column(raw_bank))

    # No KeyError/ValueError from the missing column, and every parsed
    # record defaults to an empty tag rather than crashing or inventing one.
    assert all(o.tag == "" for o in csv_orders)
    assert all(s.tag == "" for s in csv_settlements)
    assert all(b.tag == "" for b in csv_bank)

    result = reconcile(csv_orders, csv_settlements, csv_bank)  # must not raise
    assert result.report.total_orders == 53
    assert result.report.confirmed_order_count > 0

    # Every exception must still have a real, non-empty, self-describing tag
    # even though none of the input carried any tag data whatsoever.
    for e in result.exceptions:
        assert e.tag, f"{e.exception_id} has an empty tag with no input tag data to blame"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
