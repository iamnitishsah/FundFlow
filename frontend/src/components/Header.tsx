import React from 'react';
import type { Organization } from '../types';

interface HeaderProps {
  organizations: Organization[];
  selectedOrg: string;
  onSelectOrg: (slug: string) => void;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  organizations,
  selectedOrg,
  onSelectOrg,
  loading,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-500/20">
            FF
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">FundFlow</h1>
              <span className="text-xs uppercase font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Portal
              </span>
            </div>
            <p className="text-xs text-slate-400">Bank Reconciliation for Capital Calls</p>
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <label className="text-xs font-medium text-slate-400">Organization:</label>
          <div className="relative">
            <select
              value={selectedOrg}
              onChange={(e) => onSelectOrg(e.target.value)}
              disabled={loading || organizations.length === 0}
              className="appearance-none bg-slate-800 text-white text-sm font-medium rounded-lg border border-slate-700 pl-3 pr-9 py-2 hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 cursor-pointer shadow-sm transition"
            >
              {organizations.map((org) => (
                <option key={org.slug} value={org.slug}>
                  {org.name} ({org.slug})
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-slate-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

