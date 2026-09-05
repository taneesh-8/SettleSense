import { GeneratedBatch, ReconciliationResult } from './types';

// VITE_API_URL is injected at build time (set as an env var on whatever
// static host builds this — Vercel, Render, etc.). Falls back to the local
// FastAPI dev server so `npm run dev` keeps working with zero config.
const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_ROOT}/api`;

export async function generateBatch(seed: number = 42): Promise<GeneratedBatch> {
  const resp = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ seed }),
  });
  if (!resp.ok) {
    throw new Error(`Generation failed: ${resp.statusText}`);
  }
  return resp.json();
}

export async function runReconciliation(seed?: number, data?: { orders: any[]; settlements: any[]; bank: any[] }): Promise<ReconciliationResult> {
  const body = seed !== undefined ? { seed } : data;
  const resp = await fetch(`${API_BASE}/reconcile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`Reconciliation failed: ${resp.statusText}`);
  }
  return resp.json();
}

export async function uploadCSVs(ordersFile: File, settlementsFile: File, bankFile: File): Promise<ReconciliationResult> {
  const formData = new FormData();
  formData.append('orders', ordersFile);
  formData.append('settlements', settlementsFile);
  formData.append('bank', bankFile);

  const resp = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!resp.ok) {
    throw new Error(`CSV Upload failed: ${resp.statusText}`);
  }
  return resp.json();
}
