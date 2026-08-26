import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ExamSummary } from "../api/types";
import { categoryAccent } from "../lib/category";
import { daysLeft, fmtDate, fmtNum } from "../lib/dates";
import { useSavedExams } from "../lib/savedStorage";
import { statusMeta } from "../lib/status";

export default function ExamCard({ exam }: { exam: ExamSummary }) {
  const navigate = useNavigate();
  const { has, toggle } = useSavedExams();
  const [hovered, setHovered] = useState(false);
  const saved = has(exam.id);
  const status = statusMeta(exam.status);
  const [c1, c2] = categoryAccent(exam.board_category);

  const dl = daysLeft(exam.next_key_date_value);
  const urgent = dl != null && dl >= 0 && dl <= 15;

  return (
    <div
      onClick={() => navigate(`/exams/${exam.id}`)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: "#fff",
        border: "1px solid var(--color-border-neutral)",
        borderRadius: "var(--radius-card)",
        overflow: "hidden",
        cursor: "pointer",
        transition: "transform .18s ease, box-shadow .18s ease",
        transform: hovered ? "translateY(-5px)" : "translateY(0)",
        boxShadow: hovered ? "var(--shadow-card-hover)" : "var(--shadow-card-resting)",
      }}
    >
      <div
        style={{
          position: "relative",
          height: 118,
          background: `linear-gradient(135deg, ${c1}, ${c2})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 800, color: "rgba(255,255,255,.92)", letterSpacing: ".03em" }}>
          {exam.board_monogram ?? exam.name.slice(0, 4).toUpperCase()}
        </span>
        <div
          style={{
            position: "absolute",
            top: 10,
            left: 10,
            display: "inline-flex",
            alignItems: "center",
            background: status.bg,
            color: status.text,
            fontSize: 10.5,
            fontWeight: 800,
            padding: "4px 9px",
            borderRadius: "var(--radius-pill)",
          }}
        >
          {status.label}
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            e.preventDefault();
            toggle(exam.id);
          }}
          aria-label={saved ? "Remove from saved" : "Save this exam"}
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            width: 30,
            height: 30,
            borderRadius: "50%",
            background: "rgba(255,255,255,.9)",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            cursor: "pointer",
            color: saved ? "var(--color-orange-text)" : "var(--color-text-muted)",
          }}
        >
          {saved ? "♥" : "♡"}
        </button>
      </div>

      <div style={{ padding: "14px 15px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <h3 style={{ fontFamily: "var(--font-display)", fontSize: 14.5, fontWeight: 800, margin: 0, lineHeight: 1.3, color: "var(--color-navy-dark)" }}>
            {exam.name}
          </h3>
          {exam.verified && (
            <div
              title="At least one notice for this exam is independently archived"
              style={{ display: "flex", alignItems: "center", gap: 3, background: "var(--color-bg-warm-neutral)", borderRadius: 7, padding: "3px 7px", flexShrink: 0, fontSize: 10.5, fontWeight: 700, color: "var(--color-navy-primary)" }}
            >
              ✓ Verified
            </div>
          )}
        </div>
        {exam.advt_no && <p style={{ fontSize: 11.5, color: "var(--color-text-muted)", margin: 0 }}>Advt. No. {exam.advt_no}</p>}
        <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--color-text-secondary)" }}>
          <span>👥 {fmtNum(exam.vacancy_count)}</span>
          <span>🔔 {exam.notice_count}</span>
        </div>
        {exam.next_key_date_value && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 4,
              paddingTop: 9,
              borderTop: "1px solid var(--color-divider-light)",
            }}
          >
            <div>
              <div style={{ fontSize: 10, color: "var(--color-text-muted)", fontWeight: 600, textTransform: "uppercase" }}>
                {exam.next_key_date_label}
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 700, color: urgent ? "var(--color-orange-text)" : "var(--color-navy-dark)" }}>
                {fmtDate(exam.next_key_date_value)}
              </div>
            </div>
            {urgent && (
              <div style={{ background: "var(--status-closing-soon-bg)", color: "var(--color-orange-text)", fontSize: 10.5, fontWeight: 800, padding: "4px 8px", borderRadius: 7 }}>
                {dl}d left
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
