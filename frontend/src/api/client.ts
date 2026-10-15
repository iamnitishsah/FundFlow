import type {
  Organization,
  LineItem,
  BankTransaction,
  MatchProposal,
  ImportSummary,
} from '../types';

const API_BASE = '/api';

async function request<T>(
  url: string,
  options: RequestInit = {},
  orgSlug?: string
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (orgSlug) {
    headers.set('X-Organization', orgSlug);
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorMessage = errorJson.detail;
      } else if (errorJson.message) {
        errorMessage = errorJson.message;
      } else {
        errorMessage = JSON.stringify(errorJson);
      }
    } catch {
      const text = await response.text();
      if (text) errorMessage = text;
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export const api = {
  getOrganizations(): Promise<Organization[]> {
    return request<Organization[]>('/organizations/');
  },

  getLineItems(orgSlug: string): Promise<LineItem[]> {
    return request<LineItem[]>('/line-items/', {}, orgSlug);
  },

  getTransactions(orgSlug: string, statusFilter?: string): Promise<BankTransaction[]> {
    const query = statusFilter && statusFilter !== 'all' ? `?status=${statusFilter}` : '';
    return request<BankTransaction[]>(`/transactions/${query}`, {}, orgSlug);
  },

  uploadStatement(orgSlug: string, file: File): Promise<ImportSummary> {
    const formData = new FormData();
    formData.append('file', file);

    return request<ImportSummary>(
      '/statements/upload/',
      {
        method: 'POST',
        body: formData,
      },
      orgSlug
    );
  },

  approveMatch(orgSlug: string, matchId: number): Promise<MatchProposal> {
    return request<MatchProposal>(
      `/matches/${matchId}/approve/`,
      {
        method: 'POST',
      },
      orgSlug
    );
  },

  rejectMatch(orgSlug: string, matchId: number): Promise<MatchProposal> {
    return request<MatchProposal>(
      `/matches/${matchId}/reject/`,
      {
        method: 'POST',
      },
      orgSlug
    );
  },

  ignoreTransaction(orgSlug: string, transactionId: number): Promise<BankTransaction> {
    return request<BankTransaction>(
      `/transactions/${transactionId}/ignore/`,
      {
        method: 'POST',
      },
      orgSlug
    );
  },
};

