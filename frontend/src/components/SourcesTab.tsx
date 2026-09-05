import React, { useState } from 'react';
import { ShoppingCart, Landmark, Building2, Search } from 'lucide-react';
import { Order, Settlement, BankCredit } from '../types';

interface SourcesTabProps {
  orders: Order[];
  settlements: Settlement[];
  bank: BankCredit[];
}

export const SourcesTab: React.FC<SourcesTabProps> = ({ orders, settlements, bank }) => {
  const [activeSubTab, setActiveSubTab] = useState<'orders' | 'settlements' | 'bank'>('settlements');
  const [search, setSearch] = useState('');

  const filteredOrders = orders.filter(
    (o) => o.order_id.toLowerCase().includes(search.toLowerCase()) || o.customer.toLowerCase().includes(search.toLowerCase())
  );

  const filteredSettlements = settlements.filter(
    (s) => s.settlement_id.toLowerCase().includes(search.toLowerCase()) || s.utr.toLowerCase().includes(search.toLowerCase()) || s.order_id.toLowerCase().includes(search.toLowerCase())
  );

  const filteredBank = bank.filter(
    (b) => b.utr.toLowerCase().includes(search.toLowerCase()) || b.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Explanation Banner */}
      <div className="bg-gradient-to-r from-brand-900/40 via-cardbg to-cardbg border border-brand-500/20 rounded-2xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            The Three Conflicting Views of the Same Money
          </h3>
          <p className="text-xs text-slate-300">
            A ₹1,000 order never appears as ₹1,000 in the bank — it lands as ~₹976.40 inside a lump-sum payout (N orders → 1 UTR) on T+2.
          </p>
        </div>

        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search IDs, UTRs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>
      </div>

      {/* Sub-tabs selector */}
      <div className="flex items-center space-x-2 border-b border-cardborder pb-2">
        <button
          onClick={() => setActiveSubTab('orders')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeSubTab === 'orders'
              ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
              : 'bg-cardbg text-slate-400 hover:text-white border border-cardborder'
          }`}
        >
          <ShoppingCart className="w-4 h-4" />
          <span>Orders ({orders.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('settlements')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeSubTab === 'settlements'
              ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
              : 'bg-cardbg text-slate-400 hover:text-white border border-cardborder'
          }`}
        >
          <Landmark className="w-4 h-4" />
          <span>Razorpay Payouts ({settlements.length})</span>
        </button>

        <button
          onClick={() => setActiveSubTab('bank')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition ${
            activeSubTab === 'bank'
              ? 'bg-brand-600 text-white shadow-lg shadow-brand-600/30'
              : 'bg-cardbg text-slate-400 hover:text-white border border-cardborder'
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>Bank Statement ({bank.length})</span>
        </button>
      </div>

      {/* Content Table */}
      <div className="bg-cardbg border border-cardborder rounded-2xl overflow-hidden shadow-xl">
        {activeSubTab === 'orders' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
                <tr>
                  <th className="px-4 py-3">Order ID</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Method</th>
                  <th className="px-4 py-3">Amount (Gross)</th>
                  <th className="px-4 py-3">Refund</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Tag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cardborder text-slate-300">
                {filteredOrders.map((o) => (
                  <tr key={o.order_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-2.5 font-mono font-medium text-brand-400">{o.order_id}</td>
                    <td className="px-4 py-2.5">{o.customer}</td>
                    <td className="px-4 py-2.5 uppercase text-[10px] font-bold text-slate-400">{o.payment_method}</td>
                    <td className="px-4 py-2.5 font-mono font-semibold text-white">₹{(o.amount_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 font-mono text-rose-400">
                      {o.refund_paise > 0 ? `₹${(o.refund_paise / 100).toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        o.status === 'paid' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}>
                        {o.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {o.tag && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
                          {o.tag}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeSubTab === 'settlements' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
                <tr>
                  <th className="px-4 py-3">Settlement ID</th>
                  <th className="px-4 py-3">Order ID</th>
                  <th className="px-4 py-3">Gross</th>
                  <th className="px-4 py-3">MDR Fee (2%)</th>
                  <th className="px-4 py-3">GST (18%)</th>
                  <th className="px-4 py-3">TDS (1%)</th>
                  <th className="px-4 py-3">Net Expected</th>
                  <th className="px-4 py-3">Bank UTR</th>
                  <th className="px-4 py-3">Tag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cardborder text-slate-300">
                {filteredSettlements.map((s) => (
                  <tr key={s.settlement_id} className="hover:bg-slate-900/40">
                    <td className="px-4 py-2.5 font-mono font-medium text-slate-300">{s.settlement_id}</td>
                    <td className="px-4 py-2.5 font-mono text-brand-400">{s.order_id}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">₹{(s.gross_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">-₹{(s.fee_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">-₹{(s.gst_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">
                      {s.tds_paise > 0 ? `-₹${(s.tds_paise / 100).toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 font-mono font-bold text-emerald-400">₹{(s.net_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 font-mono text-brand-300 font-semibold">{s.utr}</td>
                    <td className="px-4 py-2.5">
                      {s.tag && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
                          {s.tag}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeSubTab === 'bank' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-cardborder">
                <tr>
                  <th className="px-4 py-3">Bank UTR</th>
                  <th className="px-4 py-3">Credited At</th>
                  <th className="px-4 py-3">Credit Amount</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3">Tag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cardborder text-slate-300">
                {filteredBank.map((b, idx) => (
                  <tr key={`${b.utr}-${idx}`} className="hover:bg-slate-900/40">
                    <td className="px-4 py-2.5 font-mono font-bold text-brand-300">{b.utr}</td>
                    <td className="px-4 py-2.5 text-slate-400">{b.credited_at.split('T')[0]}</td>
                    <td className="px-4 py-2.5 font-mono font-bold text-emerald-400">₹{(b.amount_paise / 100).toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-slate-300">{b.description}</td>
                    <td className="px-4 py-2.5">
                      {b.tag && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px]">
                          {b.tag}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
