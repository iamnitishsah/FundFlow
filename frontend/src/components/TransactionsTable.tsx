import React, { useState } from 'react';
import type { BankTransaction } from '../types';
import { formatMoney, formatDate } from '../utils/format';

interface TransactionsTableProps {
  transactions: BankTransaction[];
  loading: boolean;
  onApprove: (matchId: number) => Promise<void>;
  onReject: (matchId: number) => Promise<void>;
  onIgnore: (transactionId: number) => Promise<void>;
}

export const TransactionsTable: React.FC<TransactionsTableProps> = ({
  transactions,
  loading,
  onApprove,
  onReject,
  onIgnore,
}) => {
  const [filter, setFilter] = useState<string>('all');
  const [processingId, setProcessingId] = useState<string | null>(null);

  const filteredTransactions = transactions.filter((txn) => {
    if (filter === 'all') return true;
    return txn.status === filter;
  });

  const handleAction = async (actionKey: string, fn: () => Promise<void>) => {
    setProcessingId(actionKey);
    try {
      await fn();
    } finally {
      setProcessingId(null);
    }
  };

  const getStatusBadge = (status: BankTransaction['status']) => {
    switch (status) {
      case 'suggested':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Suggested
          </span>
        );
      case 'needs_review':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Needs Review
          </span>
        );
      case 'reconciled':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Reconciled
          </span>
        );
      case 'ignored':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
            Ignored
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">Bank Transactions</h2>
          <p className="text-xs text-slate-400">
            Imported bank statement entries and automated matching suggestions
          </p>
        </div>

        <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 overflow-x-auto">
          {['all', 'suggested', 'needs_review', 'reconciled', 'ignored'].map((tab) => {
            const count =
              tab === 'all'
                ? transactions.length
                : transactions.filter((t) => t.status === tab).length;

            return (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition whitespace-nowrap cursor-pointer ${
                  filter === tab
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                }`}
              >
                <span className="capitalize">{tab.replace('_', ' ')}</span>
                <span className="ml-1.5 text-[10px] opacity-75">({count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center space-y-2">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-blue-500 border-t-transparent"></div>
          <p className="text-xs text-slate-400">Loading transactions...</p>
        </div>
      ) : filteredTransactions.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-xs">
          No transactions found for the selected filter.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-2.5 px-3">Date & Ref</th>
                <th className="py-2.5 px-3">Description</th>
                <th className="py-2.5 px-3 text-right">Amount</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Suggested Match & Reason</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredTransactions.map((txn) => {
                const proposedMatches = txn.matches.filter(
                  (m) => m.match_status === 'proposed'
                );
                const approvedMatches = txn.matches.filter(
                  (m) => m.match_status === 'approved'
                );

                return (
                  <tr key={txn.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className="font-semibold text-white block">{formatDate(txn.date)}</span>
                      <span className="font-mono text-[10px] text-slate-400">
                        {txn.bank_reference}
                      </span>
                    </td>

                    <td className="py-3 px-3 max-w-xs">
                      <span className="font-medium text-slate-200 block break-words">
                        {txn.description}
                      </span>
                      <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                        {txn.type}
                      </span>
                    </td>

                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <span
                        className={`font-semibold font-mono ${
                          txn.type === 'credit' ? 'text-emerald-400' : 'text-slate-400'
                        }`}
                      >
                        {formatMoney(txn.amount)}
                      </span>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap">{getStatusBadge(txn.status)}</td>

                    <td className="py-3 px-3 max-w-sm">
                      {txn.status === 'suggested' && proposedMatches.length > 0 && (
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">
                              {proposedMatches[0].investor_name}
                            </span>
                            <span className="font-mono text-blue-400 text-[11px] px-1.5 py-0.5 rounded bg-blue-500/10">
                              {proposedMatches[0].line_item_reference}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 leading-snug">
                            {proposedMatches[0].reason}
                          </p>
                        </div>
                      )}

                      {txn.status === 'needs_review' && proposedMatches.length > 1 && (
                        <div className="space-y-2">
                          <p className="text-[11px] font-medium text-amber-300">
                            {txn.needs_review_reason}
                          </p>
                          <div className="space-y-1.5 pl-2 border-l border-amber-500/30">
                            {proposedMatches.map((match) => (
                              <div
                                key={match.id}
                                className="flex items-center justify-between gap-2 text-[11px]"
                              >
                                <div>
                                  <span className="text-white font-medium">{match.investor_name}</span>
                                  <span className="ml-1 text-blue-400 font-mono">
                                    ({match.line_item_reference})
                                  </span>
                                </div>
                                <button
                                  onClick={() =>
                                    handleAction(`approve-${match.id}`, () =>
                                      onApprove(match.id)
                                    )
                                  }
                                  disabled={processingId !== null}
                                  className="text-[10px] px-2 py-0.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-semibold cursor-pointer disabled:opacity-50"
                                >
                                  {processingId === `approve-${match.id}` ? '...' : 'Approve'}
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {txn.status === 'needs_review' && proposedMatches.length === 0 && (
                        <p className="text-[11px] text-amber-400/90 leading-snug">
                          {txn.needs_review_reason || 'No matching line items found.'}
                        </p>
                      )}

                      {txn.status === 'reconciled' && approvedMatches.length > 0 && (
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="text-emerald-400 font-semibold">Matched to:</span>
                            <span className="text-white font-medium">
                              {approvedMatches[0].investor_name}
                            </span>
                            <span className="font-mono text-emerald-400">
                              ({approvedMatches[0].line_item_reference})
                            </span>
                          </div>
                          <p className="text-[10px] text-slate-500">
                            Reconciled balance applied to capital call
                          </p>
                        </div>
                      )}

                      {txn.status === 'ignored' && (
                        <p className="text-[11px] text-slate-500 italic">
                          Transaction ignored and excluded from reconciliation
                        </p>
                      )}
                    </td>

                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1.5 justify-end">
                        {txn.status === 'suggested' && proposedMatches.length > 0 && (
                          <>
                            <button
                              onClick={() =>
                                handleAction(`approve-${proposedMatches[0].id}`, () =>
                                  onApprove(proposedMatches[0].id)
                                )
                              }
                              disabled={processingId !== null}
                              className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-[11px] font-semibold transition cursor-pointer shadow-sm"
                            >
                              {processingId === `approve-${proposedMatches[0].id}`
                                ? 'Approving...'
                                : 'Approve'}
                            </button>
                            <button
                              onClick={() =>
                                handleAction(`reject-${proposedMatches[0].id}`, () =>
                                  onReject(proposedMatches[0].id)
                                )
                              }
                              disabled={processingId !== null}
                              className="px-2.5 py-1 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 border border-rose-500/30 disabled:opacity-50 text-[11px] font-semibold transition cursor-pointer"
                            >
                              {processingId === `reject-${proposedMatches[0].id}`
                                ? 'Rejecting...'
                                : 'Reject'}
                            </button>
                            <button
                              onClick={() =>
                                handleAction(`ignore-${txn.id}`, () => onIgnore(txn.id))
                              }
                              disabled={processingId !== null}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white border border-slate-700 text-[11px] font-medium transition cursor-pointer disabled:opacity-50"
                            >
                              {processingId === `ignore-${txn.id}` ? '...' : 'Ignore'}
                            </button>
                          </>
                        )}

                        {txn.status === 'needs_review' && (
                          <button
                            onClick={() =>
                              handleAction(`ignore-${txn.id}`, () => onIgnore(txn.id))
                            }
                            disabled={processingId !== null}
                            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white border border-slate-700 text-[11px] font-medium transition cursor-pointer disabled:opacity-50"
                          >
                            {processingId === `ignore-${txn.id}` ? 'Ignoring...' : 'Ignore'}
                          </button>
                        )}

                        {txn.status === 'reconciled' && (
                          <span className="text-[11px] font-medium text-emerald-400 flex items-center gap-1">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                            </svg>
                            Reconciled
                          </span>
                        )}

                        {txn.status === 'ignored' && (
                          <span className="text-[11px] font-medium text-slate-500">
                            Ignored
                          </span>
                        )}
                      </div>
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

