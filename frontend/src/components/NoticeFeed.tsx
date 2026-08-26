import type { NoticeOut } from "../api/types";
import { fmtDate, fmtDateTime } from "../lib/dates";

export default function NoticeFeed({ notices }: { notices: NoticeOut[] }) {
  if (notices.length === 0) {
    return <p style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "20px 0" }}>No notices yet.</p>;
  }

  return (
    <div>
      {notices.map((n, i) => (
        <div key={n.id} style={{ marginTop: i > 0 ? 18 : 0, paddingTop: i > 0 ? 18 : 0, borderTop: i > 0 ? "1px solid var(--color-border-neutral)" : "none" }}>
          <p style={{ fontSize: 15, fontWeight: 600, margin: "0 0 8px", color: "var(--color-navy-dark)" }}>{n.summary_plain_language}</p>
          {(n.old_value || n.new_value) && (
            <p style={{ fontSize: 13.5, margin: "0 0 8px", display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ color: "var(--color-text-muted)", textDecoration: "line-through" }}>{n.old_value ?? "—"}</span>→
              <span style={{ color: "var(--status-open-text)", fontWeight: 600 }}>{n.new_value ?? "—"}</span>
            </p>
          )}
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: "0 0 8px" }}>
            Detected {fmtDateTime(n.detected_at)}
            {n.effective_date && ` · Effective ${fmtDate(n.effective_date)}`}
          </p>
          <p style={{ fontSize: 13, margin: "0 0 6px", color: n.archive_url ? "var(--color-navy-primary)" : "var(--color-text-muted)", fontWeight: n.archive_url ? 600 : 400 }}>
            {n.archive_url ? (
              <a href={n.archive_url} target="_blank" rel="noopener noreferrer">
                ✓ Verified archive
              </a>
            ) : (
              "Not yet independently archived"
            )}
          </p>
          <details>
            <summary style={{ fontSize: 13, color: "var(--color-navy-primary)", cursor: "pointer", fontWeight: 600 }}>See official notice</summary>
            <a href={n.source_url} target="_blank" rel="noopener noreferrer" style={{ display: "block", marginTop: 6, fontSize: 12.5, wordBreak: "break-all", color: "var(--color-text-muted)" }}>
              {n.source_url}
            </a>
          </details>
        </div>
      ))}
    </div>
  );
}
