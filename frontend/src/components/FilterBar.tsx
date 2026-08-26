import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CATEGORIES } from "../lib/category";

const QUALS = ["All", "10th Pass", "12th Pass", "Graduate", "B.Ed/D.El.Ed"];
const STATUSES = [
  { key: "All", label: "All" },
  { key: "open", label: "Open" },
  { key: "closing_soon", label: "Closing Soon" },
  { key: "closed", label: "Closed" },
  { key: "result_declared", label: "Result Declared" },
  { key: "admit_card", label: "Admit Card Out" },
  { key: "interview_scheduled", label: "Interview Scheduled" },
];

function chipStyle(active: boolean): React.CSSProperties {
  return {
    flexShrink: 0,
    whiteSpace: "nowrap",
    borderRadius: "var(--radius-pill)",
    padding: "7px 13px",
    fontSize: 12,
    fontWeight: 700,
    cursor: "pointer",
    border: `1px solid ${active ? "var(--color-navy-primary)" : "var(--color-border-neutral)"}`,
    background: active ? "var(--color-navy-primary)" : "#fff",
    color: active ? "#fff" : "var(--color-text-default)",
  };
}

export default function FilterBar({ isMobile, sticky }: { isMobile: boolean; sticky: boolean }) {
  const [params, setParams] = useSearchParams();
  const [showMore, setShowMore] = useState(false);

  const category = params.get("category") ?? "All";
  const qual = params.get("qual") ?? "All";
  const status = params.get("status") ?? "All";
  const search = params.get("q") ?? "";

  function update(patch: Record<string, string>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === "All" || !value) next.delete(key);
      else next.set(key, value);
    }
    setParams(next, { replace: true });
  }

  const hasActiveFilters = !!(search || category !== "All" || qual !== "All" || status !== "All");
  const moreFilterCount = (qual !== "All" ? 1 : 0) + (status !== "All" ? 1 : 0);

  function clearAll() {
    setParams(new URLSearchParams(), { replace: true });
  }

  return (
    <>
      <div
        style={{
          position: sticky ? "sticky" : undefined,
          top: sticky ? (isMobile ? 90 : 58) : undefined,
          zIndex: 40,
          background: "#fff",
          borderBottom: "1px solid var(--color-border-neutral)",
          padding: isMobile ? "10px 14px" : "12px 32px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          overflowX: "auto",
          boxShadow: "var(--shadow-filter-bar)",
        }}
      >
        <select
          value="Bihar"
          disabled
          title="More states coming later -- see docs/backlog.md"
          style={{
            flexShrink: 0,
            borderRadius: "var(--radius-pill)",
            padding: "7px 13px",
            fontSize: 12,
            fontWeight: 700,
            color: "var(--color-text-default)",
            border: "1px solid var(--color-border-neutral)",
            background: "#fff",
          }}
        >
          <option>📍 Bihar</option>
        </select>
        <span style={{ width: 1, height: 20, background: "var(--color-border-neutral)", flexShrink: 0 }} />

        {CATEGORIES.map((c) => (
          <button key={c.key} type="button" onClick={() => update({ category: c.key })} style={chipStyle(category === c.key)}>
            {c.icon} {c.label}
          </button>
        ))}

        <button type="button" onClick={() => setShowMore((v) => !v)} style={{ ...chipStyle(showMore), display: "flex", alignItems: "center" }}>
          ⚙ Filters
          {moreFilterCount > 0 && (
            <span style={{ background: "var(--color-orange-accent)", color: "#fff", fontSize: 10, fontWeight: 800, borderRadius: 8, padding: "1px 6px", marginLeft: 4 }}>
              {moreFilterCount}
            </span>
          )}
        </button>

        {hasActiveFilters && (
          <button type="button" onClick={clearAll} style={{ flexShrink: 0, background: "none", border: "none", color: "var(--color-orange-text)", fontSize: 12, fontWeight: 700, cursor: "pointer", textDecoration: "underline" }}>
            Clear
          </button>
        )}
      </div>

      {showMore && (
        <div style={{ background: "#fff", borderBottom: "1px solid var(--color-border-neutral)", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: "var(--color-text-muted)", marginBottom: 8, letterSpacing: ".03em" }}>QUALIFICATION</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {QUALS.map((label) => (
                <button key={label} type="button" onClick={() => update({ qual: label })} style={chipStyle(qual === label)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: "var(--color-text-muted)", marginBottom: 8, letterSpacing: ".03em" }}>APPLICATION STATUS</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {STATUSES.map((s) => (
                <button key={s.key} type="button" onClick={() => update({ status: s.key })} style={chipStyle(status === s.key)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
