import React from 'react';
import { Scale, Download, Sparkles, ShieldCheck } from 'lucide-react';
import { ReconciliationResult } from '../types';

interface HeaderProps {
  result: ReconciliationResult | null;
}

export const Header: React.FC<HeaderProps> = ({ result }) => {
  const downloadJSON = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `settlesense_reconciliation_report_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <header className="border-b border-cardborder bg-cardbg/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-brand-600/20 text-brand-500 rounded-xl border border-brand-500/30 shadow-inner">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                SettleSense
                <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-400 border border-brand-500/20 font-medium">
                  AI Finance Controller
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              3-Way Razorpay Settlement Engine • Deterministic Money Math + AI Guardrails
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="hidden sm:flex items-center space-x-2 text-xs bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800 text-slate-300">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Money = Pure Code</span>
            <span className="text-slate-600">•</span>
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>AI = Judgment Only</span>
          </div>

          <button
            onClick={downloadJSON}
            disabled={!result}
            className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition shadow ${
              result
                ? 'bg-brand-600 hover:bg-brand-500 text-white cursor-pointer active:scale-95'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            }`}
          >
            <Download className="w-4 h-4" />
            <span>Download Report (JSON)</span>
          </button>
        </div>
      </div>
    </header>
  );
};
