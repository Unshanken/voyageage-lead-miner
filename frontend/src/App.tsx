import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, ChevronDown, MailCheck, Plus, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { api } from "./api";
import { MetricStrip } from "./components/MetricStrip";
import { Sidebar } from "./components/Sidebar";
import { ImportDrawer } from "./features/companies/ImportDrawer";
import { CompanyDetail } from "./features/companies/CompanyDetail";
import { LeadTable } from "./features/companies/LeadTable";
import type { Company, ImportResult, Overview } from "./types";

const filters = [
  { label: "Score", icon: SlidersHorizontal },
  { label: "Email status", icon: MailCheck },
  { label: "Models", icon: BrainCircuit },
  { label: "AI-native", icon: BrainCircuit },
];

export default function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [crawlingIds, setCrawlingIds] = useState<Set<number>>(() => new Set());
  const [crawlRevision, setCrawlRevision] = useState(0);

  const refresh = useCallback(async (query = "") => {
    setLoading(true);
    setError(null);
    try {
      const [overviewData, companyData] = await Promise.all([api.overview(), api.companies(query)]);
      setOverview(overviewData);
      setCompanies(companyData);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the lead pipeline");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.overview(), api.companies("")])
      .then(([overviewData, companyData]) => {
        if (!cancelled) {
          setOverview(overviewData);
          setCompanies(companyData);
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Could not load the lead pipeline");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  function handleImported(result: ImportResult) {
    const message = result.errors.length
      ? `Imported ${result.created}; ${result.errors.length} row${result.errors.length === 1 ? "" : "s"} need review.`
      : `Imported ${result.created}; ${result.existing} duplicate${result.existing === 1 ? "" : "s"} merged.`;
    setNotice(message);
    setDrawerOpen(false);
    void refresh(search);
  }

  async function handleCrawl(company: Company) {
    setCrawlingIds((current) => new Set(current).add(company.id));
    setNotice(`Crawl queued for ${company.domain}.`);
    try {
      await api.crawl(company.id, Boolean(company.last_crawled_at));
      await waitForCrawl(company.id, company.last_crawled_at);
      await refresh(search);
      setCrawlRevision((value) => value + 1);
      setNotice(`Crawl completed for ${company.domain}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Crawl failed");
    } finally {
      setCrawlingIds((current) => {
        const next = new Set(current);
        next.delete(company.id);
        return next;
      });
    }
  }

  async function handleBatchCrawl() {
    try {
      const result = await api.crawlBatch(20);
      setNotice(`${result.queued} companies queued for controlled crawling.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Batch crawl could not start");
    }
  }

  return (
    <div className={`app-shell ${drawerOpen ? "drawer-open" : ""} ${selectedCompanyId !== null ? "detail-open" : ""}`}>
      <Sidebar />
      <main className="workspace">
        <header className="topbar">
          <div className="mobile-brand">VoyageAge <span>Lead Miner</span></div>
          <div className="operator">Ops User <ChevronDown size={15} /></div>
        </header>
        <div className="page-heading">
          <h1>Lead pipeline</h1>
          <div className="heading-actions"><button className="secondary-button" type="button" onClick={() => void handleBatchCrawl()}><RefreshCw size={17} />Crawl batch</button><button className="primary-button" type="button" onClick={() => setDrawerOpen(true)}><Plus size={18} />Add companies</button></div>
        </div>
        <MetricStrip data={overview} />
        <section className="pipeline-panel">
          <div className="toolbar">
            <label className="search-control"><Search size={17} /><span className="sr-only">Search companies</span><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void refresh(search)} placeholder="Search companies" /></label>
            <div className="filter-group">
              {filters.map(({ label, icon: Icon }) => <button className="filter-button" type="button" key={label}><Icon size={16} />{label}<ChevronDown size={14} /></button>)}
            </div>
          </div>
          {notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice(null)}>Dismiss</button></div>}
          {error && <div className="error-banner" role="alert">{error}<button onClick={() => void refresh()}>Retry</button></div>}
          <LeadTable companies={companies} loading={loading} crawlingIds={crawlingIds} onCrawl={(company) => void handleCrawl(company)} onView={(company) => setSelectedCompanyId(company.id)} />
          <footer className="table-footer">Showing {companies.length.toLocaleString()} companies</footer>
        </section>
      </main>
      <ImportDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onImported={handleImported} />
      <CompanyDetail key={selectedCompanyId ?? "closed"} companyId={selectedCompanyId} revision={crawlRevision} crawling={selectedCompanyId !== null && crawlingIds.has(selectedCompanyId)} onClose={() => setSelectedCompanyId(null)} onCrawl={(company) => void handleCrawl(company)} />
    </div>
  );
}

async function waitForCrawl(companyId: number, previousCrawlAt: string | null) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    const status = await api.crawlStatus(companyId);
    if (status.last_crawled_at !== previousCrawlAt && status.crawl_status !== "CRAWLING") return;
  }
  throw new Error("Crawl is still running; refresh the page to check its status.");
}
