# SettleSense — AI-Assisted Razorpay Settlement Reconciliation

**Track**: AI Finance Controller Hackathon (Razorpay)

SettleSense is a complete, working financial reconciliation platform for Razorpay merchants. It solves the core problem of **3-way money matching**: proving that customer **orders** (gross), Razorpay **settlements** (MDR fees + GST + TDS + net, grouped by UTR into payouts), and actual **bank credits** agree to the exact rupee — and when they don't, explaining *why* in plain English instead of silently dropping the mismatch.

> **For judges — the two things to look at first:**
> 1. Run `python scripts/full_audit.py` (below) — it independently recomputes every headline number from raw records and proves the report isn't lying to itself.
> 2. Open the **Matches** tab and search "UNION" — that's the coincidental-amount-collision trap, deliberately seeded and deliberately caught by the guardrail instead of being auto-matched.

---

## Why this exists

Reconciliation tools that use an LLM to "just match everything" are dangerous in finance: a hallucinated match is a real rupee that goes missing. SettleSense's design bet is the opposite — **money math is code, not AI**. AI is used only to *propose* candidates for messy leftovers (a transposed UTR digit, an unreflected refund), and a deterministic guardrail has the final word on whether a proposal is trustworthy enough to confirm. Every order in every batch is accounted for exactly once — confirmed or explained — with the underlying invariant machine-checked, not just visually plausible in a dashboard.

---

## Architecture: the 5-stage pipeline

All money is converted to **integer paise** at ingestion (₹1 = 100 paise) and never leaves that representation inside the engine — no floats cross the reconciliation boundary, so there's no rounding drift to paper over later.

```
Orders.csv ─┐
Settlements.csv ─┼─► Stage 1: Normalizer ─► Stage 2: Deterministic ─► Stage 3: Fuzzy ─► Stage 4: Guardrail ─► Stage 5: Reporter
Bank.csv ─┘        (→ integer paise)         (NO AI, pure math)      (leftovers only)   (≥2 fields or reject)  (report + audit)
```

| Stage | File | What it does |
|---|---|---|
| **1. Normalizer** | `engine/normalizer.py` | Converts every raw money field to integer paise; nothing downstream ever sees a float. |
| **2. Deterministic Matcher** | `engine/deterministic.py` | **No AI.** Recomputes expected 2% MDR fee, 18% GST-on-fee, optional 1% TDS, and net payout in integer math. **Level 1** matches Order ↔ Settlement (1-paise tolerance). **Level 2** groups settlements by UTR and matches the payout total against the bank credit. Flags unsettled orders and duplicate settlements here. |
| **3. LLM Fuzzy Matcher** | `engine/fuzzy_matcher.py` | Runs **only on what Stage 2 couldn't resolve**. Proposes matches for near-miss UTRs (Levenshtein distance) and diagnoses refunds a settlement silently ignored. Uses Anthropic Claude / Gemini if an API key is set, otherwise a fully transparent heuristic fallback — **the guardrail treats both identically**, so the demo's correctness never depends on having an LLM key. |
| **4. Guardrail** | `engine/guardrail.py` | The safety net. Accepts a proposal **only if ≥2 independent fields corroborate it** (e.g. UTR similarity *and* amount match). A proposal backed by amount alone is **rejected**, logged as an honest exception, and routed to human review — this is what stops a coincidental amount collision from being auto-matched to the wrong payout. |
| **5. Reporter** | `engine/reporter.py` | Assembles the final report: match rate, confirmed matches, exceptions with plain-language reasons, rupees reconciled/at-risk/flagged, and a full chronological audit log. Also runs two **self-check assertions** before returning anything (see below). |

### Built-in self-checks (not just tests — these run on every real request)

`reporter.build_report()` refuses to emit a report if either of these is violated:
- **No zero/negative-amount exception** — every flagged item must carry a real rupee amount, never a placeholder.
- **Tag/reason consistency** — an exception's `tag` must match its own `reason` category (e.g. anything whose reason starts with *"Orphan bank credit"* must be tagged `orphan_credit`), not an inherited label from wherever the underlying record originally came from. This exists because that exact bug shipped once (see Engineering Notes below) and shouldn't be able to silently reappear.

---

## Frontend — the dashboard

React + Vite + Tailwind + Recharts, five tabs:

| Tab | Shows |
|---|---|
| **Overview** | Headline match rate, confirmed/exceptions/₹-reconciled/₹-flagged/₹-at-risk hero cards, and a match-distribution donut + exceptions-by-stage bar chart. |
| **Sources** | The raw generated/uploaded orders, settlements, and bank credits. |
| **Matches** | The 5-stage pipeline visualized live, plus every confirmed match with its stage, method, and verification reason. |
| **Exceptions** | Every flagged record with plain-language reasoning, filterable by risk / guardrail rejection / L1-L2-L3. |
| **Audit** | The full chronological, replayable audit trail of every decision the engine made. |

All headline numbers are wired to a **single source of truth** in the backend report — the Overview hero card, its tooltip formula, and the Matches tab header all read `confirmed_order_count` / `confirmed_count` / `match_rate` off the same object, so there's no risk of the dashboard telling two different stories about the same run.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ & `npm`

### 1. Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
- Health check: `http://localhost:8000/health`
- Interactive API docs: `http://localhost:8000/docs`

### 2. Frontend (Vite + React)
```bash
cd frontend
npm install
npm run dev
```
- Open `http://localhost:5173/`
- Click **"Generate Batch & Run Pipeline"** (seed `42` reproduces every number quoted in this README)

### 3. (Optional) LLM fuzzy matching
Set either key before starting the backend to switch Stage 3 from the heuristic fallback to a real LLM call — the guardrail's acceptance criteria don't change either way:
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or GEMINI_API_KEY=...
```

---

## Verification & Testing

### Unit tests
```bash
cd backend
python -m pytest tests/ -v
```
**24/24 passing** — fee math (incl. float-drift regression), normalization, deterministic L1/L2 matching, Levenshtein distance, heuristic fuzzy matching, guardrail accept/reject rules, full-pipeline integration, and tag/reason-consistency regression tests.

### Independent audit scripts
These don't just assert — they **recompute every number from raw records** and diff against what the engine reported, so a bug in the reporting layer can't hide behind a report that only checks itself.

```bash
cd backend
python scripts/verify_order_accounting.py       # every one of the 53 seeded orders ends up
                                                 # confirmed XOR excepted — never both, never neither
python scripts/full_audit.py 42 7 100           # cross-seed: raw JSON dump, independent match_rate
                                                 # recompute, money-arithmetic recompute (rupees_reconciled,
                                                 # rupees_flagged_total, rupees_at_risk), and exact-string
                                                 # verification of every seeded edge case's classification
```
Sample output for seed 42 (`full_audit.py`):
```
[PASS] match_rate matches recompute (no rounding drift)      report=0.8679 recompute=0.8679 (46/53)
[PASS] union(confirmed, exceptions) == all 53 orders          union=53, none missing
[PASS] intersection(confirmed, exceptions) == empty            empty
[PASS] rupees_reconciled == sum(confirmed gross_paise)         report=8252061p recompute=8252061p
[PASS] rupees_flagged_total == sum(ALL exception amount_paise) report=2391880p recompute=2391880p
OVERALL: ALL PASS
```

### Ground-truth edge cases seeded into every synthetic batch (53 orders, 18+ payouts)

| Tag | Scenario | Resolves as |
|---|---|---|
| `clean_batch` | 5 orders batched into 1 UTR payout | Confirmed — deterministic |
| `mdr_gst` | Standard 2% MDR + 18% GST | Confirmed — deterministic |
| `tds_payout` | 1% TDS deducted | Confirmed — deterministic |
| `chargeback` | Payout net reduced by a chargeback | Flagged — L1 fee-math mismatch (by design: the deduction breaks the deterministic check on purpose) |
| `transposed_utr` | Bank UTR has two digits swapped | Confirmed — Stage 3 fuzzy match (UTR edit-distance + amount corroboration) |
| `refund_not_reflected` | Settlement ignores a customer refund | Flagged — Stage 3 diagnostic, amount = the refund itself, not the gross |
| `unsettled` | Order never settled | Flagged — revenue-at-risk |
| `duplicate_settlement` | Order settled twice | Flagged — duplicate exception |
| `orphan_credit` | Bank credit with no settlement at all | Flagged — orphan exception |
| `amount_collision` | A bank credit's amount coincidentally equals a *different* unmatched payout's total, with no UTR similarity | **Rejected by the guardrail** (`"insufficient corroboration (1 field): amount-only match rejected..."`) — never silently auto-matched, never misfiled as a plain orphan |

---

## API Reference

- `POST /api/generate` `{ "seed": 42 }` — generates a synthetic Razorpay-shaped dataset (orders, settlements, bank credits) without running reconciliation.
- `POST /api/reconcile` `{ "seed": 42 }` **or** `{ "orders": [...], "settlements": [...], "bank": [...] }` — runs the full 5-stage engine and returns the complete `ReconciliationResult`.
- `POST /api/upload` *(multipart)* — accepts `orders.csv`, `settlements.csv`, `bank.csv` and returns the same shape as `/api/reconcile`.

`ReconciliationResult` shape (see `frontend/src/types.ts` for the exact TypeScript mirror — kept field-for-field in sync with the backend Pydantic models):
```
{
  report: { total_orders, confirmed_count, confirmed_order_count, exception_count,
            match_rate, rupees_reconciled, rupees_at_risk, rupees_flagged_total,
            paise_reconciled, paise_at_risk, paise_flagged_total, stage_counts, fuzzy_mode },
  confirmed: [ { match_id, order_ids, settlement_ids, utr, bank_utr, gross_paise,
                 net_paise, bank_paise, stage, method, reason } ],
  exceptions: [ { exception_id, record_type, record_id, level, stage, reason,
                  amount_paise, risk_flag, tag, order_ids } ],
  audit_log: [ { seq, stage, action, record_id, detail, ai_used } ],
  orders, settlements, bank   // normalized, integer-paise records
}
```

---

## Project Structure

```
SettleSense/
├── backend/
│   ├── engine/
│   │   ├── generator.py       # synthetic Razorpay-shaped data + seeded edge cases
│   │   ├── normalizer.py      # Stage 1 — float → integer paise
│   │   ├── deterministic.py   # Stage 2 — L1/L2 matching, no AI
│   │   ├── fuzzy_matcher.py   # Stage 3 — LLM / heuristic proposals on leftovers only
│   │   ├── guardrail.py       # Stage 4 — ≥2-field corroboration or reject
│   │   ├── reporter.py        # Stage 5 — report assembly + self-check assertions
│   │   ├── pipeline.py        # orchestrates all 5 stages
│   │   └── models.py          # Pydantic schemas (raw, normalized, and output)
│   ├── scripts/
│   │   ├── verify_order_accounting.py   # 53-orders-in, 53-orders-accounted-for proof
│   │   └── full_audit.py                # cross-seed money + classification audit
│   ├── tests/test_engine.py   # 24 unit + integration tests
│   └── main.py                 # FastAPI app (/api/generate, /api/reconcile, /api/upload)
└── frontend/
    └── src/
        ├── components/         # OverviewTab, SourcesTab, MatchesTab, ExceptionsTab, AuditTab
        ├── api.ts               # typed fetch wrappers to the backend
        └── types.ts             # TypeScript mirror of the backend Pydantic models
```

---

## Engineering notes (what makes this more than a demo)

A few defects were found and fixed during hardening, each with a regression test or standalone audit script added so the same class of bug can't quietly come back:

- **Match-rate numerator confusion**: the dashboard once risked showing a *group count* (payout batches) where an *order count* was expected. Fixed by making `confirmed_order_count` (orders) and `confirmed_count` (batches) two explicitly distinct, consistently-labeled fields everywhere they're displayed — headline, tooltip, hero card, and the Matches tab header all read from the same two fields.
- **Amount-collision credit slipping past the guardrail**: the heuristic fuzzy matcher only checked amount-corroboration against a bank credit's *UTR-nearest* settlement group — so a credit whose amount coincidentally matched a *different* group's payout was never even proposed as a match, and fell through as a generic orphan instead of a guardrail rejection. Fixed by checking amount-corroboration against every unmatched group, not just the nearest one.
- **Silent order drops in exception accounting**: `Exception_` records had no `order_ids` field, so a guardrail-rejected *group* of orders (e.g. 3 orders in one rejected payout) was invisible to per-order accounting even though it was correctly flagged. Fixed by adding `order_ids` to every exception, populated so that a losing proposal never double-claims orders a winning rival proposal already confirmed. `scripts/verify_order_accounting.py` makes this guarantee checkable on demand.
- **Tag/reason mismatch**: a true orphan bank credit was tagged with whichever seeded batch it originally came from (e.g. `refund_not_reflected`) instead of what it actually is (`orphan_credit`). Fixed at the source, plus a `reporter.py` assertion and a dedicated test so a tag can never again silently drift from its own reason string.

---

## License

Built for the Razorpay AI Finance Controller Hackathon.
