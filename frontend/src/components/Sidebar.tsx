import { Ban, Building2, LayoutDashboard, Upload } from "lucide-react";

const navigation = [
  { label: "Overview", icon: LayoutDashboard, active: true },
  { label: "Companies", icon: Building2 },
  { label: "Suppression", icon: Ban },
  { label: "Exports", icon: Upload },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">✦</span>
        <div>
          <strong>VoyageAge</strong>
          <span>Lead Miner</span>
        </div>
      </div>
      <nav aria-label="Primary navigation">
        {navigation.map(({ label, icon: Icon, active }) => (
          <button className={`nav-item ${active ? "active" : ""}`} key={label} type="button">
            <Icon size={19} strokeWidth={1.75} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="team-switcher">Operations Team</div>
    </aside>
  );
}

