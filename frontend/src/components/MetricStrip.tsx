import type { Overview } from "../types";

const metricKeys: Array<{ key: keyof Overview; label: string }> = [
  { key: "companies_discovered", label: "Companies discovered" },
  { key: "companies_analyzed", label: "Companies analyzed" },
  { key: "high_fit_leads", label: "High-fit leads" },
  { key: "verified_contacts", label: "Verified contacts" },
  { key: "export_ready", label: "Export-ready" },
];

export function MetricStrip({ data }: { data: Overview | null }) {
  return (
    <section className="metric-strip" aria-label="Lead pipeline overview">
      {metricKeys.map(({ key, label }) => (
        <div className="metric" key={key}>
          <span>{label}</span>
          <strong>{data ? data[key].toLocaleString() : "—"}</strong>
        </div>
      ))}
    </section>
  );
}

