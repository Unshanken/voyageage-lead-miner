export type EmailStatus = "unknown" | "valid" | "risky" | "invalid" | "accept_all";

export interface Contact {
  id: number;
  full_name: string | null;
  title: string | null;
  email: string | null;
  email_status: EmailStatus;
}

export interface LeadSource {
  source: string;
  source_url: string | null;
}

export interface Company {
  id: number;
  company_name: string | null;
  domain: string;
  website_url: string;
  description: string | null;
  ai_native: boolean | null;
  ai_native_candidate: boolean;
  llm_dependency: string | null;
  providers_detected: string[];
  models_detected: string[];
  ai_signals: string[];
  ai_signal_count: number;
  strong_ai_signal_count: number;
  weak_ai_signal_count: number;
  has_api_docs: boolean;
  has_ai_docs: boolean;
  has_multiple_models: boolean;
  has_ai_pricing_signal: boolean;
  has_ai_jobs_signal: boolean;
  llm_integration_signal: boolean;
  crawl_status: string;
  last_crawled_at: string | null;
  crawl_duration_ms: number | null;
  crawl_summary: Record<string, unknown>;
  voyageage_fit_score: number;
  fit_reason: string | null;
  pipeline_status: string;
  error_message: string | null;
  created_at: string;
  contacts: Contact[];
  sources: LeadSource[];
}

export interface CrawledPage {
  id: number;
  url: string;
  normalized_url: string;
  canonical_url: string | null;
  page_type: string;
  status_code: number | null;
  content_type: string | null;
  title: string | null;
  meta_description: string | null;
  h1: string | null;
  crawl_status: string;
  error_code: string | null;
  error_message: string | null;
  discovered_from: string | null;
  depth: number;
  signal_count: number;
  crawled_at: string | null;
}

export interface SignalEvidence {
  id: number;
  page_id: number;
  signal_type: string;
  signal_key: string;
  value: string;
  evidence_text: string;
  source_url: string;
  confidence: number;
  context: string;
  detector: string;
}

export interface CrawlStatus {
  company_id: number;
  domain: string;
  crawl_status: string;
  pipeline_status: string;
  last_crawled_at: string | null;
  crawl_duration_ms: number | null;
  summary: Record<string, unknown>;
  error_message: string | null;
}

export interface Overview {
  companies_discovered: number;
  companies_analyzed: number;
  high_fit_leads: number;
  verified_contacts: number;
  export_ready: number;
}

export interface ImportResult {
  created: number;
  existing: number;
  sources_added: number;
  errors: Array<{ row: number; value: string; message: string }>;
}
