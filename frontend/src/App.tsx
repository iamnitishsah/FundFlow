import { useState, useEffect, useCallback } from 'react';
import type { Organization, LineItem, BankTransaction, ImportSummary } from './types';
import { api } from './api/client';
import { Header } from './components/Header';
import { LineItemsPanel } from './components/LineItemsPanel';
import { CsvUploader } from './components/CsvUploader';
import { TransactionsTable } from './components/TransactionsTable';

export function App() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<string>('northwind');
  const [lineItems, setLineItems] = useState<LineItem[]>([]);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState<boolean>(true);
  const [loadingData, setLoadingData] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => {
      setNotification((curr) => (curr?.message === message ? null : curr));
    }, 5000);
  };

  const loadOrganizations = async () => {
    setLoadingOrgs(true);
    try {
      const orgs = await api.getOrganizations();
      setOrganizations(orgs);
      if (orgs.length > 0 && !orgs.some((o) => o.slug === selectedOrg)) {
        setSelectedOrg(orgs[0].slug);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        showNotification('error', `Failed to load organizations: ${err.message}`);
      }
    } finally {
      setLoadingOrgs(false);
    }
  };

  const loadOrgData = useCallback(async (orgSlug: string) => {
    if (!orgSlug) return;
    setLoadingData(true);
    try {
      const [items, txns] = await Promise.all([
        api.getLineItems(orgSlug),
        api.getTransactions(orgSlug),
      ]);
      setLineItems(items);
      setTransactions(txns);
    } catch (err: unknown) {
      if (err instanceof Error) {
        showNotification('error', `Failed to load organization data: ${err.message}`);
      }
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    loadOrganizations();
  }, []);

  useEffect(() => {
    if (selectedOrg) {
      loadOrgData(selectedOrg);
    }
  }, [selectedOrg, loadOrgData]);

  const handleUpload = async (file: File): Promise<ImportSummary> => {
    setIsUploading(true);
    try {
      const summary = await api.uploadStatement(selectedOrg, file);
      await loadOrgData(selectedOrg);
      showNotification(
        'success',
        `Processed statement: ${summary.imported_count} imported, ${summary.duplicate_count} duplicates skipped, ${summary.error_count} row errors.`
      );
      return summary;
    } finally {
      setIsUploading(false);
    }
  };

  const handleApprove = async (matchId: number) => {
    try {
      await api.approveMatch(selectedOrg, matchId);
      await loadOrgData(selectedOrg);
      showNotification('success', 'Match successfully approved and line item funded.');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showNotification('error', err.message);
      }
    }
  };

  const handleReject = async (matchId: number) => {
    try {
      await api.rejectMatch(selectedOrg, matchId);
      await loadOrgData(selectedOrg);
      showNotification('success', 'Match rejected.');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showNotification('error', err.message);
      }
    }
  };

  const handleIgnore = async (transactionId: number) => {
    try {
      await api.ignoreTransaction(selectedOrg, transactionId);
      await loadOrgData(selectedOrg);
      showNotification('success', 'Transaction marked as ignored.');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showNotification('error', err.message);
      }
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        organizations={organizations}
        selectedOrg={selectedOrg}
        onSelectOrg={(slug) => setSelectedOrg(slug)}
        loading={loadingOrgs}
      />

      {notification && (
        <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 mt-4">
          <div
            className={`p-3.5 rounded-xl text-xs font-medium flex items-center justify-between border shadow-sm ${
              notification.type === 'success'
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                : 'bg-red-500/10 text-red-300 border-red-500/20'
            }`}
          >
            <div className="flex items-center gap-2">
              {notification.type === 'success' ? (
                <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-4 h-4 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              <span>{notification.message}</span>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="opacity-75 hover:opacity-100 text-xs px-2 py-0.5 ml-4"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6 flex-1">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2">
            <LineItemsPanel lineItems={lineItems} loading={loadingData} />
          </div>
          <div>
            <CsvUploader onUpload={handleUpload} isUploading={isUploading} />
          </div>
        </div>

        <TransactionsTable
          transactions={transactions}
          loading={loadingData}
          onApprove={handleApprove}
          onReject={handleReject}
          onIgnore={handleIgnore}
        />
      </main>

      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        FundFlow — Bank Reconciliation for Capital Calls
      </footer>
    </div>
  );
}

export default App;