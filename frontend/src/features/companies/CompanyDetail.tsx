import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw, X } from "lucide-react";
import { api } from "../../api";
import type { Company, CrawledPage, SignalEvidence } from "../../types";

interface DetailData {
  company: Company;
  pages: CrawledPage[];
  signals: SignalEvidence[];
}

export function CompanyDetail({
  companyId,
  revision,
  crawling,
  onClose,
  onCrawl,
}: {
  companyId: number | null;
  revision: number;
  crawling: boolean;
  onClose: () => void;
  onCrawl: (company: Company) => void;
}) {
  const [data, setData] = useState<DetailData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (companyId === null) return;
    let cancelled = false;
    Promise.all([api.company(companyId), api.pages(companyId), api.signals(companyId)])
      .then(([company, pages, signals]) => {
        if (!cancelled) {
          setError(null);
          setData({ company, pages, signals });
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not load company details");
      });
    return () => { cancelled = true; };
  }, [companyId, revision]);

  if (companyId === null) return null;
  const company = data?.company;
  const summary = company?.crawl_summary;

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="drawer detail-drawer" role="dialog" aria-modal="true" aria-labelledby="company-detail-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="drawer-header">
          <div><h2 id="company-detail-title">{company?.company_name || company?.domain || "Company details"}</h2>{company && <a className="detail-domain" href={company.website_url} target="_blank" rel="noreferrer">{company.domain}<ExternalLink size={12} /></a>}</div>
          <button className="icon-button" onClick={onClose} aria-label="Close company details"><X size={21} /></button>
        </header>
        <div className="detail-body">
          {error && <div className="error-banner">{error}</div>}
          {!data && !error && <div className="table-state">Loading crawl details…</div>}
          {data && (
            <>
              <section className="detail-section crawl-summary">
                <div className="detail-section-heading"><h3>Crawl summary</h3><button className="secondary-button compact" disabled={crawling} onClick={() => onCrawl(data.company)}><RefreshCw size={15} className={crawling ? "spinning" : ""} />{data.company.last_crawled_at ? "Re-crawl" : "Crawl"}</button></div>
                <dl className="summary-grid">
                  <div><dt>Pages crawled</dt><dd>{String(summary?.pages_crawled ?? 0)}</dd></div>
                  <div><dt>Pages failed</dt><dd>{String(summary?.pages_failed ?? 0)}</dd></div>
                  <div><dt>Pages skipped</dt><dd>{String(summary?.pages_skipped ?? 0)}</dd></div>
                  <div><dt>Duration</dt><dd>{formatDuration(data.company.crawl_duration_ms)}</dd></div>
                  <div><dt>Last crawled</dt><dd>{formatDate(data.company.last_crawled_at)}</dd></div>
                </dl>
                {data.company.error_message && <p className="crawl-error">{data.company.error_message}</p>}
              </section>
              <section className="detail-section"><h3>Models and providers</h3><div className="tag-list">{[...data.company.providers_detected, ...data.company.models_detected].map((item) => <span className="signal-tag" key={item}>{item}</span>)}{!data.company.providers_detected.length && !data.company.models_detected.length && <span className="muted">No models or providers detected.</span>}</div></section>
              <section className="detail-section"><h3>Evidence</h3><div className="evidence-list">{data.signals.map((signal) => <article className="evidence-item" key={signal.id}><div><strong>{signal.signal_key.replaceAll("_", " ")}</strong><span>{signal.context.replaceAll("_", " ")} · {Math.round(signal.confidence * 100)}%</span></div><p>{signal.evidence_text}</p><a href={signal.source_url} target="_blank" rel="noreferrer">Source page<ExternalLink size={11} /></a></article>)}{!data.signals.length && <p className="muted">No deterministic AI signals found.</p>}</div></section>
              <section className="detail-section"><h3>Pages</h3><div className="page-list">{data.pages.map((page) => <article className="page-item" key={page.id}><span className="page-type">{page.page_type}</span><div><a href={page.normalized_url} target="_blank" rel="noreferrer">{page.title || page.normalized_url}</a><small>{page.crawl_status} · HTTP {page.status_code ?? "—"} · {page.error_code ? `${page.error_code} · ` : ""}{page.signal_count} signals</small></div></article>)}{!data.pages.length && <p className="muted">No pages crawled yet.</p>}</div></section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Never";
}

function formatDuration(value: number | null) {
  return value === null ? "—" : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}
