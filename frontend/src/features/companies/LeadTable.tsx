import { ExternalLink, RefreshCw } from "lucide-react";
import type { Company } from "../../types";

export function LeadTable({
  companies,
  loading,
  crawlingIds,
  onCrawl,
  onView,
}: {
  companies: Company[];
  loading: boolean;
  crawlingIds: Set<number>;
  onCrawl: (company: Company) => void;
  onView: (company: Company) => void;
}) {
  if (loading) return <div className="table-state">Loading companies…</div>;
  if (!companies.length) {
    return (
      <div className="empty-state">
        <strong>No companies yet</strong>
        <span>Add a website, paste domains, or import a CSV to start the pipeline.</span>
      </div>
    );
  }

  return (
    <div className="table-scroll">
      <table className="lead-table">
        <thead>
          <tr>
            <th>Company</th><th>Crawl status</th><th>AI signals</th><th>Models / providers</th>
            <th>Last crawled</th><th>Source</th><th>Pipeline</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((company) => {
            const source = company.sources[0];
            const isCrawling = crawlingIds.has(company.id) || company.crawl_status === "CRAWLING";
            return (
              <tr key={company.id}>
                <td className="company-cell">
                  <strong>{company.company_name || company.domain}</strong>
                  <a href={company.website_url} target="_blank" rel="noreferrer">
                    {company.domain}<ExternalLink size={12} aria-hidden="true" />
                  </a>
                </td>
                <td><span className={`crawl-state state-${company.crawl_status.toLowerCase()}`}>{isCrawling ? "CRAWLING" : company.crawl_status}</span></td>
                <td><strong>{company.strong_ai_signal_count}</strong> strong · {company.weak_ai_signal_count} weak</td>
                <td>{[...company.providers_detected, ...company.models_detected].slice(0, 4).join(", ") || "—"}</td>
                <td>{formatDate(company.last_crawled_at)}</td>
                <td>{source?.source || "—"}</td>
                <td><span className="status">{company.pipeline_status.replaceAll("_", " ")}</span></td>
                <td className="row-actions">
                  <button type="button" className="text-button" onClick={() => onView(company)}>View details</button>
                  <button type="button" className="icon-action" disabled={isCrawling} onClick={() => onCrawl(company)} aria-label={`${company.last_crawled_at ? "Re-crawl" : "Crawl"} ${company.domain}`}>
                    <RefreshCw size={15} className={isCrawling ? "spinning" : ""} />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
