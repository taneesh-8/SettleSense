import { GeneratedBatch, ReconciliationResult } from './types';

// VITE_API_URL is injected at build time (set as an env var on whatever
// static host builds this — Vercel, Render, etc.) and gets BAKED INTO the
// bundle at `npm run build` time, not read at runtime. If you set/change
// this env var on Vercel after the last deploy, you must trigger a new
// build — updating the dashboard value alone does nothing until then.
const API_ROOT = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_BASE = `${API_ROOT}/api`;

// Fail loudly instead of silently falling back to localhost in production —
// if VITE_API_URL wasn't actually baked into this build, every API call
// would otherwise fail with an unexplained "Failed to fetch" and no hint
// as to why. This makes the misconfiguration visible in the browser
// console immediately on page load.
if (typeof window !== 'undefined') {
  const isLocalPage = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
  if (!isLocalPage && API_ROOT.includes('localhost')) {
    console.error(
      `[SettleSense] VITE_API_URL was not baked into this build — falling back to ` +
      `${API_ROOT}, which is unreachable from a deployed site. Set VITE_API_URL on ` +
      `the host (e.g. Vercel) and trigger a new deploy — updating the env var alone ` +
      `does not affect an already-built bundle.`
    );
  }
  // Mixed content: an https page can never successfully fetch a plain http://
  // API — the browser blocks it before the request is even sent. This is a
  // silent "Failed to fetch" with no CORS error in the console, easy to
  // mistake for a CORS issue.
  if (window.location.protocol === 'https:' && API_ROOT.startsWith('http://')) {
    console.error(
      `[SettleSense] Mixed content: this page is served over https but ` +
      `VITE_API_URL (${API_ROOT}) is http. The browser will block every request. ` +
      `Set VITE_API_URL to the backend's https:// URL and redeploy.`
    );
  }
}

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
