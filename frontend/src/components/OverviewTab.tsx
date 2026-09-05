import React, { useState } from 'react';
import { 
  CheckCircle2, AlertTriangle, IndianRupee, ShieldAlert, Sparkles, Upload, Play, RefreshCw, FileSpreadsheet 
} from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ReconciliationResult } from '../types';

interface OverviewTabProps {
  result: ReconciliationResult | null;
  loading: boolean;
  onGenerateAndReconcile: (seed: number) => void;
  onUploadCSVs: (orders: File, settlements: File, bank: File) => void;
  seed: number;
  setSeed: (s: number) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  result,
  loading,
  onGenerateAndReconcile,
  onUploadCSVs,
  seed,
  setSeed,
}) => {
  const [ordersFile, setOrdersFile] = useState<File | null>(null);
  const [settlementsFile, setSettlementsFile] = useState<File | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ordersFile && settlementsFile && bankFile) {
      onUploadCSVs(ordersFile, settlementsFile, bankFile);
    }
  };

  const report = result?.report;

  // Donut chart data
  const pieData = report ? [
    { name: 'Confirmed Matches', value: report.confirmed_count, color: '#10b981' },
    { name: 'Exceptions', value: report.exception_count, color: '#f59e0b' },
  ] : [];

  // Bar chart data for exceptions by stage
  const stageData = result ? Object.entries(
    result.exceptions.reduce((acc, curr) => {
      const stage = curr.stage.replace('_deterministic', '').replace('_fuzzy_', ' ');
      acc[stage] = (acc[stage] || 0) + 1;
      return acc;
    }, {} as Record<string, number>)
  ).map(([name, count]) => ({ name, count })) : [];

  return (
    <div className="space-y-6">
      {/* Action Bar & Data Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Synthetic Generator Panel */}
        <div className="lg:col-span-2 bg-cardbg border border-cardborder rounded-2xl p-5 shadow-xl relative overflow-hidden">
          <div className="absolute -top-12 -right-12 w-40 h-40 bg-brand-500/10 rounded-full blur-2xl pointer-events-none" />
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 rounded-xl bg-brand-500/20 text-brand-400">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white">Razorpay Synthetic Batch Generator</h3>
                <p className="text-xs text-slate-400">Generates 53+ orders, 18 payouts, and tagged financial edge cases</p>
              </div>
            </div>
            <span className="text-xs font-mono bg-slate-900 text-brand-400 px-2.5 py-1 rounded-md border border-slate-800">
              53 Orders • 18 Payouts
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center space-x-2 bg-slate-900 px-3 py-2 rounded-xl border border-slate-800">
              <label className="text-xs font-medium text-slate-400">Seed:</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
                className="w-20 bg-transparent text-white font-mono text-sm focus:outline-none"
              />
            </div>

            <button
              onClick={() => onGenerateAndReconcile(seed)}
              disabled={loading}
              className="flex-1 min-w-[200px] flex items-center justify-center space-x-2 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm px-5 py-2.5 rounded-xl transition shadow-lg shadow-brand-600/30 active:scale-[0.98] disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4 fill-current" />
              )}
              <span>{loading ? 'Reconciling Engine...' : 'Generate Batch & Run Pipeline'}</span>
            </button>
          </div>
        </div>

        {/* CSV Dropzone Panel */}
        <div className="bg-cardbg border border-cardborder rounded-2xl p-5 shadow-xl">
          <div className="flex items-center space-x-2.5 mb-3">
            <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Upload 3 CSV Files</h3>
              <p className="text-xs text-slate-400">Orders, Settlements, Bank credits</p>
            </div>
          </div>

          <form onSubmit={handleUploadSubmit} className="space-y-2 text-xs">
            <div className="grid grid-cols-3 gap-2">
              <label className={`p-2 border rounded-xl flex flex-col items-center justify-center text-center cursor-pointer transition ${ordersFile ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700'}`}>
                <Upload className="w-3.5 h-3.5 mb-1" />
                <span className="truncate w-full font-medium">{ordersFile ? ordersFile.name : 'Orders CSV'}</span>
                <input type="file" accept=".csv" onChange={(e) => setOrdersFile(e.target.files?.[0] || null)} className="hidden" />
              </label>

              <label className={`p-2 border rounded-xl flex flex-col items-center justify-center text-center cursor-pointer transition ${settlementsFile ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700'}`}>
                <Upload className="w-3.5 h-3.5 mb-1" />
                <span className="truncate w-full font-medium">{settlementsFile ? settlementsFile.name : 'Settlements CSV'}</span>
                <input type="file" accept=".csv" onChange={(e) => setSettlementsFile(e.target.files?.[0] || null)} className="hidden" />
              </label>

              <label className={`p-2 border rounded-xl flex flex-col items-center justify-center text-center cursor-pointer transition ${bankFile ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300' : 'border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700'}`}>
                <Upload className="w-3.5 h-3.5 mb-1" />
                <span className="truncate w-full font-medium">{bankFile ? bankFile.name : 'Bank CSV'}</span>
                <input type="file" accept=".csv" onChange={(e) => setBankFile(e.target.files?.[0] || null)} className="hidden" />
              </label>
            </div>

            <button
              type="submit"
              disabled={!ordersFile || !settlementsFile || !bankFile || loading}
              className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 font-semibold py-2 rounded-xl text-xs transition border border-slate-700"
            >
              Reconcile CSVs
            </button>
          </form>
        </div>
      </div>

      {/* Hero Metric Cards */}
      {report && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {/* Card 1: Match Rate */}
          <div 
            className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden group cursor-help"
            title={`Formula: Confirmed Matched Orders (${report.confirmed_order_count ?? report.confirmed_count ?? 0}) ÷ Total Input Orders (${report.total_orders ?? 0})`}
          >
            <div className="text-xs font-semibold text-slate-400 mb-1 flex items-center justify-between">
              <span>Match Rate</span>
              <span className="text-[10px] text-brand-400 bg-brand-500/10 px-1.5 py-0.5 rounded font-mono">Formula ℹ</span>
            </div>
            <div className="text-3xl font-black text-white flex items-baseline gap-1 font-mono">
              {((report.match_rate ?? 0) * 100).toFixed(1)}
              <span className="text-lg text-brand-400">%</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-medium">
              {report.confirmed_order_count ?? report.confirmed_count ?? 0} of {report.total_orders ?? 0} total orders matched
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-emerald-500/10 text-emerald-400 rounded-xl">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>

          {/* Card 2: Confirmed Orders */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden">
            <div className="text-xs font-semibold text-slate-400 mb-1">Confirmed Orders</div>
            <div className="text-3xl font-black text-emerald-400 font-mono">
              {report.confirmed_order_count ?? report.confirmed_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-medium">
              Across {report.confirmed_count ?? 0} payout batches
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-emerald-500/10 text-emerald-400 rounded-xl">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>

          {/* Card 3: Honest Exceptions */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden">
            <div className="text-xs font-semibold text-slate-400 mb-1">Honest Exceptions</div>
            <div className="text-3xl font-black text-amber-400 font-mono">
              {report.exception_count ?? 0}
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-medium">
              Requires human review
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-amber-500/10 text-amber-400 rounded-xl">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          {/* Card 4: ₹ Reconciled */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden">
            <div className="text-xs font-semibold text-slate-400 mb-1">₹ Reconciled</div>
            <div className="text-xl font-black text-white font-mono flex items-center">
              <IndianRupee className="w-4 h-4 mr-0.5 text-slate-400" />
              {(report.rupees_reconciled ?? 0).toLocaleString('en-IN')}
            </div>
            <div className="text-[11px] text-slate-400 mt-1 font-medium">
              Proven 3-way balance
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-brand-500/10 text-brand-400 rounded-xl">
              <IndianRupee className="w-5 h-5" />
            </div>
          </div>

          {/* Card 5: Total Flagged for Review */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden">
            <div className="text-xs font-semibold text-amber-300 mb-1">Total Flagged for Review</div>
            <div className="text-xl font-black text-amber-400 font-mono flex items-center">
              <IndianRupee className="w-4 h-4 mr-0.5 text-amber-400" />
              {(report.rupees_flagged_total ?? (report.paise_flagged_total ? report.paise_flagged_total / 100 : 0)).toLocaleString('en-IN')}
            </div>
            <div className="text-[11px] text-amber-300/70 mt-1 font-medium">
              Sum of all exceptions
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-amber-500/10 text-amber-400 rounded-xl">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          {/* Card 6: Unsettled Revenue at Risk */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-4 shadow-md relative overflow-hidden">
            <div className="text-xs font-semibold text-rose-300 mb-1">Unsettled Revenue at Risk</div>
            <div className="text-xl font-black text-rose-400 font-mono flex items-center">
              <IndianRupee className="w-4 h-4 mr-0.5 text-rose-400" />
              {(report.rupees_at_risk ?? 0).toLocaleString('en-IN')}
            </div>
            <div className="text-[11px] text-rose-300/70 mt-1 font-medium">
              Unsettled orders only
            </div>
            <div className="absolute right-3 bottom-3 p-2 bg-rose-500/10 text-rose-400 rounded-xl">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
        </div>
      )}



      {/* Visual Analytics Grid */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Donut Chart: Confirmed vs Exceptions */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-5 shadow-xl">
            <h3 className="text-sm font-bold text-white mb-1">Match Distribution</h3>
            <p className="text-xs text-slate-400 mb-4">Confirmed matches vs exceptions flagged across all stages</p>
            <div className="h-64 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} stroke="#141a26" strokeWidth={3} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f141f', borderColor: '#273146', borderRadius: '12px', color: '#fff' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center space-x-6 text-xs mt-2">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-slate-300">Confirmed ({report?.confirmed_count})</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-slate-300">Exceptions ({report?.exception_count})</span>
              </div>
            </div>
          </div>

          {/* Bar Chart: Exceptions by Stage */}
          <div className="bg-cardbg border border-cardborder rounded-2xl p-5 shadow-xl">
            <h3 className="text-sm font-bold text-white mb-1">Exceptions Breakdown by Stage</h3>
            <p className="text-xs text-slate-400 mb-4">Which engine stage flagged each exception</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stageData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#212a3e" />
                  <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} interval={0} />
                  <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f141f', borderColor: '#273146', borderRadius: '12px', color: '#fff' }}
                  />
                  <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
