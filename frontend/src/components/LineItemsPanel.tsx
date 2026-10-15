import React from 'react';
import type { LineItem } from '../types';
import { formatMoney, formatDate } from '../utils/format';

interface LineItemsPanelProps {
  lineItems: LineItem[];
  loading: boolean;
}

export const LineItemsPanel: React.FC<LineItemsPanelProps> = ({ lineItems, loading }) => {
  const totalCalled = lineItems.reduce((acc, item) => acc + parseFloat(item.amount_called), 0);
  const totalFunded = lineItems.reduce((acc, item) => acc + parseFloat(item.amount_funded), 0);
  const totalRemaining = totalCalled - totalFunded;
  const fundedPercent = totalCalled > 0 ? Math.round((totalFunded / totalCalled) * 100) : 0;

  const getStatusBadge = (status: LineItem['status']) => {
    switch (status) {
      case 'funded':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Funded
          </span>
        );
      case 'partially_funded':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Partially Funded
          </span>
        );
      case 'open':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Open
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-5">
      <div>
        <h2 className="text-base font-semibold text-white">Capital Call Line Items</h2>
        <p className="text-xs text-slate-400">
          Target funding requests issued to Limited Partners
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <span className="text-xs text-slate-400 font-medium block">Total Called</span>
          <span className="text-lg font-bold text-white tracking-tight">
            {formatMoney(totalCalled)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Total Funded</span>
            <span className="text-[11px] font-semibold text-emerald-400">{fundedPercent}%</span>
          </div>
          <span className="text-lg font-bold text-emerald-400 tracking-tight">
            {formatMoney(totalFunded)}
          </span>
        </div>
        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60">
          <span className="text-xs text-slate-400 font-medium block">Remaining</span>
          <span className="text-lg font-bold text-amber-400 tracking-tight">
            {formatMoney(totalRemaining)}
          </span>
        </div>
      </div>

      {loading ? (
        <div className="py-10 text-center space-y-2">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-blue-500 border-t-transparent"></div>
          <p className="text-xs text-slate-400">Loading line items...</p>
        </div>
      ) : lineItems.length === 0 ? (
        <div className="py-8 text-center text-slate-500 text-xs">
          No line items found for this organization.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-2.5 px-3">Call</th>
                <th className="py-2.5 px-3">Investor Entity</th>
                <th className="py-2.5 px-3">Wire Ref</th>
                <th className="py-2.5 px-3 text-right">Called</th>
                <th className="py-2.5 px-3 text-right">Funded</th>
                <th className="py-2.5 px-3 text-right">Remaining</th>
                <th className="py-2.5 px-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {lineItems.map((item) => {
                const called = parseFloat(item.amount_called);
                const funded = parseFloat(item.amount_funded);
                const pct = called > 0 ? Math.min(100, Math.round((funded / called) * 100)) : 0;

                return (
                  <tr key={item.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="font-semibold text-white">#{item.call_number}</span>
                      <span className="text-[10px] text-slate-500 block">
                        {formatDate(item.call_date)}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-medium text-white block">{item.investor_name}</span>
                    </td>
                    <td className="py-3 px-3 font-mono font-medium text-blue-400">
                      {item.wire_reference}
                    </td>
                    <td className="py-3 px-3 text-right font-medium text-slate-200">
                      {formatMoney(item.amount_called)}
                    </td>
                    <td className="py-3 px-3 text-right font-medium text-emerald-400">
                      {formatMoney(item.amount_funded)}
                      <div className="w-16 h-1.5 bg-slate-800 rounded-full ml-auto mt-1 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right font-semibold text-amber-400">
                      {formatMoney(item.amount_remaining)}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {getStatusBadge(item.status)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

