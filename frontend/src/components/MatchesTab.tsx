import React, { useState } from 'react';
import { CheckCircle2, ArrowRight, Sparkles, Shield, Cpu, Search } from 'lucide-react';
import { ConfirmedMatch, ReconciliationReport } from '../types';

interface MatchesTabProps {
  confirmed: ConfirmedMatch[];
  report: ReconciliationReport | null;
}

export const MatchesTab: React.FC<MatchesTabProps> = ({ confirmed, report }) => {
  const [search, setSearch] = useState('');

  const filteredMatches = confirmed.filter(
    (m) =>
      m.match_id.toLowerCase().includes(search.toLowerCase()) ||
      m.utr.toLowerCase().includes(search.toLowerCase()) ||
      m.reason.toLowerCase().includes(search.toLowerCase()) ||
      m.order_ids.some(o => o.toLowerCase().includes(search.toLowerCase()))
  );

  const stageCounts = report?.stage_counts || {};

  return (
    <div className="space-y-6">
      {/* 5-Stage Pipeline Visualizer */}
      <div className="bg-cardbg border border-cardborder rounded-2xl p-5 shadow-xl">
        <h3 className="text-sm font-bold text-white mb-1">5-Stage Reconciliation Pipeline Architecture</h3>
        <p className="text-xs text-slate-400 mb-6">Trace how each record was processed and resolved through the engine</p>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
          {/* Stage 1 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
                <span>STAGE 1</span>
                <Cpu className="w-3.5 h-3.5 text-slate-500" />
              </div>
              <h4 className="text-xs font-bold text-white mb-1">Normalizer</h4>
              <p className="text-[11px] text-slate-400 leading-tight">Converts money to integer paise, strips IDs & dates</p>
            </div>
            <div className="mt-4 pt-2 border-t border-slate-800/60 text-xs font-mono font-semibold text-slate-300">
              {report?.total_orders || 0} Orders Parsed
            </div>
          </div>

          {/* Stage 2 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between relative">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
                <span>STAGE 2</span>
                <span className="text-[9px] font-bold bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded">NO AI</span>
              </div>
              <h4 className="text-xs font-bold text-white mb-1">Deterministic</h4>
              <p className="text-[11px] text-slate-400 leading-tight">L1 fee math & L2 exact UTR payout matching</p>
            </div>
            <div className="mt-4 pt-2 border-t border-slate-800/60 text-xs font-mono font-semibold text-emerald-400">
              {stageCounts['L1_deterministic'] || stageCounts['L2_deterministic'] || 0} Cleared
            </div>
          </div>

          {/* Stage 3 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
                <span>STAGE 3</span>
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              </div>
              <h4 className="text-xs font-bold text-white mb-1">LLM Fuzzy</h4>
              <p className="text-[11px] text-slate-400 leading-tight">Reasons about messy cases (transposed UTRs)</p>
            </div>
            <div className="mt-4 pt-2 border-t border-slate-800/60 text-xs font-mono font-semibold text-amber-400">
              Mode: {report?.fuzzy_mode || 'heuristic'}
            </div>
          </div>

          {/* Stage 4 */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
                <span>STAGE 4</span>
                <Shield className="w-3.5 h-3.5 text-purple-400" />
              </div>
              <h4 className="text-xs font-bold text-white mb-1">Guardrail</h4>
              <p className="text-[11px] text-slate-400 leading-tight">Enforces ≥2 fields rule, rejects amount-only</p>
            </div>
            <div className="mt-4 pt-2 border-t border-slate-800/60 text-xs font-mono font-semibold text-purple-400">
              Strict Verification
            </div>
          </div>

          {/* Stage 5 */}
          <div className="bg-brand-950/40 border border-brand-500/30 rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs text-brand-400 font-mono mb-2">
                <span>STAGE 5</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <h4 className="text-xs font-bold text-white mb-1">Final Reporting</h4>
              <p className="text-[11px] text-slate-400 leading-tight">Summary stats, audit trail, exception output</p>
            </div>
            <div className="mt-4 pt-2 border-t border-brand-500/20 text-xs font-mono font-bold text-emerald-400">
              {(report?.match_rate ? report.match_rate * 100 : 0).toFixed(1)}% Match Rate
            </div>
          </div>
        </div>
      </div>

      {/* Confirmed Matches Header + Search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            Confirmed 3-Way Matches ({report?.confirmed_order_count || 0} Orders across {confirmed.length} Batches)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Resolved across Deterministic (L1 & L2) and Stage 3 LLM/Fuzzy stages
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search orders, UTRs, reasons..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {/* Confirmed Matches Table */}
      <div className="bg-cardbg border border-cardborder rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
              <tr>
                <th className="px-4 py-3">Match ID</th>
                <th className="px-4 py-3">Matched Orders</th>
                <th className="px-4 py-3">Bank UTR</th>
                <th className="px-4 py-3">Stage & Method</th>
                <th className="px-4 py-3">Net Reconciled</th>
                <th className="px-4 py-3">Verification Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cardborder text-slate-300">
              {filteredMatches.map((m) => {
                const isFuzzy = m.method.includes('fuzzy') || m.stage.includes('fuzzy');
                return (
                  <tr key={m.match_id} className={`hover:bg-slate-900/40 ${isFuzzy ? 'bg-purple-950/20' : ''}`}>
                    <td className="px-4 py-3 font-mono font-medium text-emerald-400">{m.match_id}</td>
                    <td className="px-4 py-3 font-mono text-slate-300">
                      <div className="flex flex-wrap gap-1">
                        {m.order_ids.map((oid) => (
                          <span key={oid} className="bg-slate-800 text-brand-300 px-1.5 py-0.5 rounded text-[10px]">
                            {oid}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-white">{m.bank_utr}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                          isFuzzy
                            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30 shadow-sm'
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}
                      >
                        {isFuzzy && <Sparkles className="w-3 h-3 text-amber-400" />}
                        {m.stage} ({m.method})
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-white">
                      ₹{(m.net_paise / 100).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-medium">
                      {m.reason}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

        </div>
      </div>
    </div>
  );
};
