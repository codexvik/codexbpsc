import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AlertItem } from "../api/types";
import { relativeTime } from "../lib/dates";

export default function NotificationsStrip({ isMobile }: { isMobile: boolean }) {
  const navigate = useNavigate();
  const [items, setItems] = useState<AlertItem[] | null>(null);

  useEffect(() => {
    api.recentNotices(8).then(setItems).catch(() => setItems([]));
  }, []);

  if (!items || items.length === 0) return null;

  return (
    <div style={{ background: "#fff", borderBottom: "1px solid var(--color-border-neutral)", padding: isMobile ? "9px 14px" : "10px 32px" }}>
      <div style={{ maxWidth: "var(--maxw-home)", margin: "0 auto", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 15, flexShrink: 0 }}>🔔</span>
        <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 16 : 26, overflowX: "auto", overflowY: "hidden", flex: 1 }}>
          {items.map((n) => (
            <div
              key={n.id}
              onClick={() => navigate(`/exams/${n.exam_id}`)}
              style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0, cursor: "pointer", padding: "4px 0" }}
            >
              <span style={{ fontSize: 12.5, color: "var(--color-navy-dark)", fontWeight: 600, whiteSpace: "nowrap" }}>
                {n.exam_name}: {n.summary_plain_language}
              </span>
              <span style={{ fontSize: 11, color: "var(--color-text-muted)" }}>· {relativeTime(n.detected_at)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
