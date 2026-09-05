"""
SettleSense FastAPI Backend
POST /api/generate   — generate synthetic data
POST /api/reconcile  — run reconciliation (with data or seed)
POST /api/upload     — multipart CSV upload
GET  /health         — health check
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.generator import generate
from engine.models import RawOrder, RawSettlement, RawBankCredit
from engine.normalizer import parse_csv_orders, parse_csv_settlements, parse_csv_bank
from engine.pipeline import reconcile

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("settlesense")

app = FastAPI(
    title="SettleSense API",
    description="AI-assisted Razorpay settlement reconciliation",
    version="1.0.0",
)

# CORS: FRONTEND_URL is set as an env var in production (the deployed
# frontend's URL — e.g. a Vercel or Render URL). Falls back to the local
# Vite dev server ports so nothing breaks for local development when the
# env var isn't set. Supports a comma-separated list so both a production
# URL and a preview-deployment URL (e.g. Vercel preview builds) can be
# allowed at once.
_default_origins = ["http://localhost:5173", "http://localhost:5174",
                     "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
_frontend_url = os.environ.get("FRONTEND_URL", "")
_allow_origins = [o.strip() for o in _frontend_url.split(",") if o.strip()] or _default_origins
if _frontend_url:
    # Keep local dev origins usable even when FRONTEND_URL is set (e.g. a
    # developer pointing their local backend at a deployed FRONTEND_URL).
    _allow_origins = list(dict.fromkeys(_allow_origins + _default_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    seed: int = 42


class ReconcileRequest(BaseModel):
    seed: Optional[int] = None
    orders: Optional[List[dict]] = None
    settlements: Optional[List[dict]] = None
    bank: Optional[List[dict]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_orders_from_dicts(data: List[dict]) -> List[RawOrder]:
    return [RawOrder(**d) for d in data]


def _raw_settlements_from_dicts(data: List[dict]) -> List[RawSettlement]:
    return [RawSettlement(**d) for d in data]


def _raw_bank_from_dicts(data: List[dict]) -> List[RawBankCredit]:
    return [RawBankCredit(**d) for d in data]


def _orders_to_dicts(orders: List[RawOrder]) -> List[dict]:
    return [o.model_dump() for o in orders]


def _settlements_to_dicts(settlements: List[RawSettlement]) -> List[dict]:
    return [s.model_dump() for s in settlements]


def _bank_to_dicts(bank: List[RawBankCredit]) -> List[dict]:
    return [b.model_dump() for b in bank]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    orders, settlements, bank = generate(seed=req.seed)
    return {
        "seed": req.seed,
        "orders": _orders_to_dicts(orders),
        "settlements": _settlements_to_dicts(settlements),
        "bank": _bank_to_dicts(bank),
        "counts": {
            "orders": len(orders),
            "settlements": len(settlements),
            "bank": len(bank),
        },
    }


@app.post("/api/reconcile")
def api_reconcile(req: ReconcileRequest):
    if req.seed is not None:
        raw_orders, raw_settlements, raw_bank = generate(seed=req.seed)
    elif req.orders is not None and req.settlements is not None and req.bank is not None:
        try:
            raw_orders = _raw_orders_from_dicts(req.orders)
            raw_settlements = _raw_settlements_from_dicts(req.settlements)
            raw_bank = _raw_bank_from_dicts(req.bank)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Data parsing error: {e}")
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'seed' or all three of 'orders', 'settlements', 'bank'"
        )

    logger.info(f"Running reconciliation: {len(raw_orders)} orders, "
                f"{len(raw_settlements)} settlements, {len(raw_bank)} bank credits")

    result = reconcile(raw_orders, raw_settlements, raw_bank)
    return result.model_dump()


@app.post("/api/upload")
async def api_upload(
    orders: UploadFile = File(...),
    settlements: UploadFile = File(...),
    bank: UploadFile = File(...),
):
    try:
        orders_content = (await orders.read()).decode("utf-8-sig")
        settlements_content = (await settlements.read()).decode("utf-8-sig")
        bank_content = (await bank.read()).decode("utf-8-sig")

        orders_rows = list(csv.DictReader(io.StringIO(orders_content)))
        settlements_rows = list(csv.DictReader(io.StringIO(settlements_content)))
        bank_rows = list(csv.DictReader(io.StringIO(bank_content)))

        raw_orders = parse_csv_orders(orders_rows)
        raw_settlements = parse_csv_settlements(settlements_rows)
        raw_bank = parse_csv_bank(bank_rows)

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CSV parsing error: {e}")

    logger.info(f"CSV upload reconciliation: {len(raw_orders)} orders")
    result = reconcile(raw_orders, raw_settlements, raw_bank)
    return result.model_dump()


if __name__ == "__main__":
    # Local dev entrypoint (python main.py). Render's start command
    # (uvicorn main:app --host 0.0.0.0 --port $PORT) doesn't go through
    # this block, but we honor $PORT here too for consistency.
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
