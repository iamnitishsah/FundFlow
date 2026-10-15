export interface Organization {
  id: number;
  slug: string;
  name: string;
}

export type LineItemStatus = 'open' | 'partially_funded' | 'funded';

export interface LineItem {
  id: number;
  wire_reference: string;
  normalized_reference: string;
  amount_called: string;
  amount_funded: string;
  amount_remaining: string;
  status: LineItemStatus;
  investor_name: string;
  call_number: number;
  call_date: string;
}

export type MatchStatus = 'proposed' | 'approved' | 'rejected';

export interface MatchProposal {
  id: number;
  line_item: number;
  line_item_reference: string;
  investor_name: string;
  line_item_remaining: string;
  match_status: MatchStatus;
  reason: string;
  created_at: string;
}

export type TransactionStatus = 'suggested' | 'needs_review' | 'reconciled' | 'ignored';
export type TransactionType = 'credit' | 'debit';

export interface BankTransaction {
  id: number;
  date: string;
  description: string;
  amount: string;
  type: TransactionType;
  bank_reference: string;
  status: TransactionStatus;
  needs_review_reason: string;
  raw_file_line: number | null;
  matches: MatchProposal[];
  suggested_match: MatchProposal | null;
}

export interface RowError {
  line: number;
  message: string;
}

export interface DuplicateRow {
  line: number;
  reference: string;
  message: string;
}

export interface ImportSummary {
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  errors: RowError[];
  duplicates: DuplicateRow[];
  transactions?: BankTransaction[];
}

