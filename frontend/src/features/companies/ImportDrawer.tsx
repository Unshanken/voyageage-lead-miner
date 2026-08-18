import { useState } from "react";
import { Upload, X } from "lucide-react";
import { api } from "../../api";
import type { ImportResult } from "../../types";

type Mode = "single" | "batch" | "csv";

export function ImportDrawer({
  open,
  onClose,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  onImported: (result: ImportResult) => void;
}) {
  const [mode, setMode] = useState<Mode>("batch");
  const [value, setValue] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      let result: ImportResult;
      if (mode === "csv") {
        if (!file) throw new Error("Choose a CSV file first.");
        result = await api.importCsv(file);
      } else if (mode === "single") {
        if (!value.trim()) throw new Error("Enter a website or domain.");
        result = await api.addSingle(value.trim());
      } else {
        const websites = value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        if (!websites.length) throw new Error("Paste at least one website or domain.");
        result = await api.addBatch(websites);
      }
      setValue("");
      setFile(null);
      onImported(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="drawer-header">
          <h2 id="drawer-title">Add companies</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close import panel"><X size={21} /></button>
        </header>
        <div className="tabs" role="tablist" aria-label="Import method">
          {(["single", "batch", "csv"] as Mode[]).map((tab) => (
            <button key={tab} type="button" role="tab" aria-selected={mode === tab} className={mode === tab ? "selected" : ""} onClick={() => setMode(tab)}>
              {tab[0].toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
        <div className="drawer-body">
          {mode === "csv" ? (
            <label className="file-drop">
              <Upload size={24} aria-hidden="true" />
              <strong>{file?.name || "Choose company CSV"}</strong>
              <span>UTF-8, maximum 5 MB</span>
              <input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </label>
          ) : (
            <label className="field-label">
              Website URL
              {mode === "single" ? (
                <input autoFocus value={value} onChange={(event) => setValue(event.target.value)} placeholder="example-ai-startup.com" />
              ) : (
                <textarea autoFocus value={value} onChange={(event) => setValue(event.target.value)} placeholder={"Paste one URL or domain per line\nexample.ai\nnorthstar.ai"} maxLength={20000} />
              )}
            </label>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
          <p className="privacy-note">Only public B2B company data is accepted. Duplicate domains are merged with source provenance.</p>
        </div>
        <footer className="drawer-footer">
          <button className="secondary-button" type="button" onClick={onClose}>Cancel</button>
          <button className="primary-button" type="button" disabled={busy} onClick={submit}>{busy ? "Importing…" : "Import companies"}</button>
        </footer>
      </aside>
    </div>
  );
}

