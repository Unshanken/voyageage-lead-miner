import type {
  Company,
  CrawledPage,
  CrawlStatus,
  ImportResult,
  Overview,
  SignalEvidence,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "Request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  overview: () => request<Overview>("/api/overview"),
  companies: (search = "") =>
    request<Company[]>(`/api/companies?search=${encodeURIComponent(search)}`),
  company: (companyId: number) => request<Company>(`/api/companies/${companyId}`),
  crawl: (companyId: number, force = false) =>
    request<{ queued: number }>(`/api/companies/${companyId}/crawl?force=${force}`, {
      method: "POST",
    }),
  crawlBatch: (limit = 20) =>
    request<{ queued: number }>("/api/companies/crawl-batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit }),
    }),
  crawlStatus: (companyId: number) =>
    request<CrawlStatus>(`/api/companies/${companyId}/crawl`),
  pages: (companyId: number) =>
    request<CrawledPage[]>(`/api/companies/${companyId}/pages`),
  signals: (companyId: number) =>
    request<SignalEvidence[]>(`/api/companies/${companyId}/signals`),
  addSingle: (website: string) =>
    request<ImportResult>("/api/companies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ website }),
    }),
  addBatch: (websites: string[]) =>
    request<ImportResult>("/api/companies/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ websites }),
    }),
  importCsv: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<ImportResult>("/api/companies/import-csv", { method: "POST", body });
  },
};
