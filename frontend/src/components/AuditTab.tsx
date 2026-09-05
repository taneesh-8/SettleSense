import React, { useState } from 'react';
import { History, Shield, Sparkles, Cpu, CheckCircle2, Search } from 'lucide-react';
import { AuditEntry } from '../types';

interface AuditTabProps {
  auditLog: AuditEntry[];
}

export const AuditTab: React.FC<AuditTabProps> = ({ auditLog }) => {
  const [search, setSearch] = useState('');

  const filteredLog = auditLog.filter(
    (a) =>
      a.stage.toLowerCase().includes(search.toLowerCase()) ||
      a.action.toLowerCase().includes(search.toLowerCase()) ||
      a.record_id.toLowerCase().includes(search.toLowerCase()) ||
      a.detail.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Design Philosophy Callout Banner */}
      <div className="bg-gradient-to-r from-brand-950 via-cardbg to-cardbg border border-brand-500/30 rounded-2xl p-5 shadow-xl">
        <div className="flex items-center space-x-2 text-brand-400 font-bold text-sm mb-2">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Core Design Decision: "Money Math is Code, Not AI"</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs mt-3">
          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800 space-y-1">
            <div className="flex items-center space-x-2 font-semibold text-emerald-400">
              <Cpu className="w-4 h-4" />
              <span>1. Pure Deterministic Math</span>
            </div>
            <p className="text-slate-400 text-[11px]">
              All MDR (2%), GST (18%), TDS (1%), and net calculations run in integer paise code. Zero LLM involvement in fee arithmetic.
            </p>
          </div>

          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800 space-y-1">
            <div className="flex items-center space-x-2 font-semibold text-amber-400">
              <Sparkles className="w-4 h-4" />
              <span>2. AI for Judgment Only</span>
            </div>
            <p className="text-slate-400 text-[11px]">
              LLM/Heuristic runs ONLY on leftover unmatched records to reason about transposed UTRs and un-reflected refunds.
            </p>
          </div>

          <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800 space-y-1">
            <div className="flex items-center space-x-2 font-semibold text-purple-400">
              <Shield className="w-4 h-4" />
              <span>3. Strict Verification Guardrail</span>
            </div>
            <p className="text-slate-400 text-[11px]">
              Accepts AI proposals ONLY if ≥2 independent fields corroborate. Rejects coincidental amount matches automatically.
            </p>
          </div>
        </div>
      </div>

      {/* Audit Log Header + Search */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <History className="w-4 h-4 text-brand-400" />
          Ordered Execution Decision Log ({auditLog.length} steps)
        </h3>

        <div className="relative w-full sm:w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search actions, IDs, details..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {/* Decision Log Table */}
      <div className="bg-cardbg border border-cardborder rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Stage</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target ID</th>
                <th className="px-4 py-3">Execution Detail</th>
                <th className="px-4 py-3">Engine Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cardborder text-slate-300 font-mono">
              {filteredLog.map((entry) => (
                <tr key={entry.seq} className="hover:bg-slate-900/40">
                  <td className="px-4 py-2.5 text-slate-500 font-bold">{entry.seq}</td>
                  <td className="px-4 py-2.5 text-brand-400 font-semibold">{entry.stage}</td>
                  <td className="px-4 py-2.5 text-white font-medium">{entry.action}</td>
                  <td className="px-4 py-2.5 text-amber-300">{entry.record_id}</td>
                  <td className="px-4 py-2.5 font-sans text-slate-300 text-[11px] leading-relaxed">
                    {entry.detail}
                  </td>
                  <td className="px-4 py-2.5">
                    {entry.ai_used ? (
                      <span className="inline-flex items-center space-x-1 bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded text-[10px] font-sans font-semibold border border-amber-500/20">
                        <Sparkles className="w-3 h-3" />
                        <span>AI Judgment</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1 bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-sans font-semibold border border-emerald-500/20">
                        <Cpu className="w-3 h-3" />
                        <span>Deterministic Code</span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
