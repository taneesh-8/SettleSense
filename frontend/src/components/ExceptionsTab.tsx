import React, { useState } from 'react';
import { AlertTriangle, ShieldAlert, Filter, Info, ShieldCheck } from 'lucide-react';
import { ExceptionItem } from '../types';

interface ExceptionsTabProps {
  exceptions: ExceptionItem[];
}

export const ExceptionsTab: React.FC<ExceptionsTabProps> = ({ exceptions }) => {
  const [filterLevel, setFilterLevel] = useState<string>('ALL');

  const filtered = exceptions.filter((e) => {
    if (filterLevel === 'ALL') return true;
    if (filterLevel === 'RISK') return e.risk_flag;
    if (filterLevel === 'GUARDRAIL') return e.level === 'guardrail' || e.stage === 'guardrail';
    return e.level === filterLevel;
  });

  return (
    <div className="space-y-4">
      {/* Header Info */}
      <div className="bg-cardbg border border-cardborder rounded-2xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Honest Exceptions & Rejections List ({exceptions.length})
          </h3>
          <p className="text-xs text-slate-400">
            Records that could not be verified automatically with 100% confidence. Routed to human workflow.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex items-center space-x-1.5 bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setFilterLevel('ALL')}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filterLevel === 'ALL' ? 'bg-brand-600 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            All ({exceptions.length})
          </button>
          <button
            onClick={() => setFilterLevel('RISK')}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filterLevel === 'RISK' ? 'bg-rose-600 text-white' : 'text-rose-400 hover:text-white'
            }`}
          >
            Revenue Risk ({exceptions.filter(e => e.risk_flag).length})
          </button>
          <button
            onClick={() => setFilterLevel('GUARDRAIL')}
            className={`px-3 py-1 rounded-lg font-medium transition ${
              filterLevel === 'GUARDRAIL' ? 'bg-amber-600 text-white' : 'text-amber-400 hover:text-white'
            }`}
          >
            Guardrail Rejections
          </button>
        </div>
      </div>

      {/* Exception Table */}
      <div className="bg-cardbg border border-cardborder rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
              <tr>
                <th className="px-4 py-3">Exception ID</th>
                <th className="px-4 py-3">Record ID</th>
                <th className="px-4 py-3">Level</th>
                <th className="px-4 py-3">Flagging Stage</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Plain-Language Diagnosis & Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-cardborder text-slate-300">
              {filtered.map((exc) => {
                const isRevenueRisk = exc.risk_flag;
                const isGuardrailReject = exc.level === 'guardrail' || exc.stage === 'guardrail' || exc.tag === 'amount_collision';

                return (
                  <tr
                    key={exc.exception_id}
                    className={`transition ${
                      isRevenueRisk
                        ? 'bg-rose-500/10 hover:bg-rose-500/15 border-l-4 border-l-rose-500'
                        : isGuardrailReject
                        ? 'bg-amber-500/10 hover:bg-amber-500/15 border-l-4 border-l-amber-500'
                        : 'hover:bg-slate-900/40'
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-slate-400 font-medium">{exc.exception_id}</td>
                    <td className="px-4 py-3 font-mono font-bold text-white">{exc.record_id}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          exc.level === 'L1'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : exc.level === 'L2'
                            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        {exc.level}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                      {exc.stage}
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-white">
                      ₹{(exc.amount_paise / 100).toFixed(2)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-start space-x-2">
                        {isRevenueRisk ? (
                          <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        ) : isGuardrailReject ? (
                          <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        ) : (
                          <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                        )}
                        <div>
                          <p className={`font-medium ${isRevenueRisk ? 'text-rose-200' : isGuardrailReject ? 'text-amber-200' : 'text-slate-200'}`}>
                            {exc.reason}
                          </p>
                          {isGuardrailReject && (
                            <span className="inline-block mt-1 text-[10px] bg-amber-950 text-amber-300 px-2 py-0.5 rounded border border-amber-800">
                              🛡️ Coincidental-Amount Collision Trap Prevented
                            </span>
                          )}
                          {isRevenueRisk && (
                            <span className="inline-block mt-1 text-[10px] bg-rose-950 text-rose-300 px-2 py-0.5 rounded border border-rose-800">
                              ⚠️ Revenue at Risk — Order Unsettled
                            </span>
                          )}
                        </div>
                      </div>
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
