export interface SignalReason {
  type: "new_class" | "filing_cluster" | "long_filing_gap" | "novel_tokens";
  points: number;
  explanation: string;
  evidence: Record<string, string | number | string[] | number[]>;
}

export interface FilingSignal {
  signal_id: string;
  trademark_number: string;
  applicant_id: string;
  applicant_name: string;
  mark_text: string;
  filing_date: string | null;
  detected_at: string;
  score: number;
  maximum_score: number;
  algorithm_version: string;
  status: string;
  classes: number[];
  reasons: SignalReason[];
  official_record_url: string | null;
  evidence_path: string;
}

export interface TrademarkEvent {
  event_id: string;
  event_type: string;
  event_category: string;
  effective_date: string | null;
  declared_date: string | null;
  is_standing: boolean;
}

export interface Trademark {
  trademark_number: string;
  applicant_id: string;
  applicant_name: string;
  observed_applicant_name: string;
  mark_text: string | null;
  mark_types: string[];
  filing_date: string | null;
  priority_date: string | null;
  current_status: string;
  classes: Array<{ class_number: number; goods_services_text: string | null }>;
  events: TrademarkEvent[];
  source_hash: string;
  source_dataset_url: string;
  official_record_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
  is_demo: boolean;
}

export interface ApplicantSummary {
  applicant_id: string;
  display_name: string;
  categories: string[];
  filings: number;
  signals: number;
  classes: Array<{ class_number: number; filings: number }>;
  latest_filing_date: string | null;
  trademark_numbers: string[];
}

export interface ObservedChange {
  change_id: string;
  trademark_number: string;
  change_type: string;
  detected_at: string;
  old_value: string | null;
  new_value: string | null;
  before_source_hash: string | null;
  after_source_hash: string;
  summary: string;
}

export interface Dashboard {
  project: string;
  generated_at: string;
  is_demo: boolean;
  disclaimer: string;
  source: {
    name: string;
    publisher: string;
    url: string;
    license: string;
    adaptation_notice: string;
  };
  stats: {
    watched_organisations: number;
    matched_organisations: number;
    trade_marks: number;
    signals: number;
    observed_changes: number;
    classes: number;
    privacy_quarantined: number;
  };
  reason_counts: Record<string, number>;
  class_counts: Array<{ class_number: number; filings: number }>;
  signals: FilingSignal[];
  applicants: ApplicantSummary[];
  trademarks: Trademark[];
  changes: ObservedChange[];
}
