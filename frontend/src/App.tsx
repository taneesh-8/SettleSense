import React, { useEffect, useState } from 'react';
import { LayoutDashboard, Layers, AlertTriangle, CheckCircle2, History, AlertCircle } from 'lucide-react';
import { Header } from './components/Header';
import { OverviewTab } from './components/OverviewTab';
import { SourcesTab } from './components/SourcesTab';
import { ExceptionsTab } from './components/ExceptionsTab';
import { MatchesTab } from './components/MatchesTab';
import { AuditTab } from './components/AuditTab';
import { runReconciliation, uploadCSVs } from './api';
import { ReconciliationResult } from './types';

export function App() {
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'sources' | 'exceptions' | 'matches' | 'audit'>('overview');
  const [seed, setSeed] = useState<number>(42);

  const fetchReconciliation = async (currentSeed: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await runReconciliation(currentSeed);
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to connect to backend engine');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadCSVs = async (orders: File, settlements: File, bank: File) => {
    setLoading(true);
    setError(null);
    try {
      const data = await uploadCSVs(orders, settlements, bank);
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'CSV reconciliation failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReconciliation(seed);
  }, []);

  return (
    <div className="min-h-screen bg-slatebg flex flex-col font-sans">
      <Header result={result} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs Bar */}
        <div className="flex items-center space-x-1 border-b border-cardborder overflow-x-auto no-scrollbar pb-1">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
              activeTab === 'overview'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab('sources')}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
              activeTab === 'sources'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Three Sources</span>
          </button>

          <button
            onClick={() => setActiveTab('exceptions')}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap relative ${
              activeTab === 'exceptions'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Exceptions</span>
            {result && result.exceptions.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-amber-500 text-slate-950 font-extrabold rounded-full">
                {result.exceptions.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('matches')}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
              activeTab === 'matches'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Matches & Flow</span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
              activeTab === 'audit'
                ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Audit Trail</span>
          </button>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="bg-rose-500/10 border border-rose-500/30 rounded-2xl p-4 flex items-center space-x-3 text-rose-300 text-xs">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <div className="flex-1">
              <span className="font-bold">Error:</span> {error}
            </div>
            <button
              onClick={() => fetchReconciliation(seed)}
              className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Tab Contents */}
        {activeTab === 'overview' && (
          <OverviewTab
            result={result}
            loading={loading}
            onGenerateAndReconcile={fetchReconciliation}
            onUploadCSVs={handleUploadCSVs}
            seed={seed}
            setSeed={setSeed}
          />
        )}

        {activeTab === 'sources' && (
          <SourcesTab
            orders={result?.orders || []}
            settlements={result?.settlements || []}
            bank={result?.bank || []}
          />
        )}

        {activeTab === 'exceptions' && (
          <ExceptionsTab exceptions={result?.exceptions || []} />
        )}

        {activeTab === 'matches' && (
          <MatchesTab confirmed={result?.confirmed || []} report={result?.report || null} />
        )}

        {activeTab === 'audit' && (
          <AuditTab auditLog={result?.audit_log || []} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-cardborder py-4 text-center text-xs text-slate-500 mt-auto">
        <p>SettleSense — AI Finance Controller Hackathon • Built with FastAPI, Integer Paise Math & React 18</p>
      </footer>
    </div>
  );
}
