import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { ExamSummary } from "../api/types";
import { categoryAccent } from "../lib/category";
import { fmtDate } from "../lib/dates";
import { useAppliedExams, useSavedExams } from "../lib/savedStorage";

export default function Saved() {
  const navigate = useNavigate();
  const { ids: savedIds, toggle: toggleSave } = useSavedExams();
  const { has: isApplied, toggle: toggleApplied } = useAppliedExams();
  const [exams, setExams] = useState<ExamSummary[]>([]);

  useEffect(() => {
    api.listExams().then((all) => setExams(all.filter((e) => savedIds.has(e.id))));
  }, [savedIds]);

  return (
    <div style={{ maxWidth: "var(--maxw-saved)", margin: "0 auto", padding: "32px 32px 70px" }}>
      <h1 style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 800, margin: "0 0 4px" }}>Saved exams &amp; tracker</h1>
      <p style={{ fontSize: 13, color: "var(--color-text-muted)", margin: "0 0 22px" }}>
        आपकी सहेजी गई परीक्षाएँ — mark exams you've applied to and track them here.
      </p>

      {exams.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {exams.map((ex) => {
            const [c1, c2] = categoryAccent(ex.board_category);
            const applied = isApplied(ex.id);
            return (
              <div key={ex.id} style={{ background: "#fff", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-card-sm)", padding: "14px 16px", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                <div style={{ width: 46, height: 46, borderRadius: 10, background: `linear-gradient(135deg, ${c1}, ${c2})`, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 12.5, flexShrink: 0 }}>
                  {ex.board_monogram ?? ex.name.slice(0, 4).toUpperCase()}
                </div>
                <div style={{ flex: 1, cursor: "pointer", minWidth: 150 }} onClick={() => navigate(`/exams/${ex.id}`)}>
                  <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--color-navy-dark)" }}>{ex.name}</div>
                  {ex.next_key_date_value && <div style={{ fontSize: 11.5, color: "var(--color-text-muted)", marginTop: 2 }}>{ex.next_key_date_label}: {fmtDate(ex.next_key_date_value)}</div>}
                </div>
                <button
                  type="button"
                  onClick={() => toggleApplied(ex.id)}
                  style={{
                    borderRadius: 8,
                    padding: "8px 12px",
                    fontSize: 11.5,
                    fontWeight: 700,
                    cursor: "pointer",
                    border: `1px solid ${applied ? "var(--status-open-text)" : "var(--color-border-neutral)"}`,
                    background: applied ? "var(--status-open-bg)" : "#fff",
                    color: applied ? "var(--status-open-text)" : "var(--color-text-default)",
                  }}
                >
                  {applied ? "✓ Applied" : "Mark Applied"}
                </button>
                <button type="button" onClick={() => toggleSave(ex.id)} style={{ background: "none", border: "none", fontSize: 16, cursor: "pointer", color: "var(--color-orange-text)" }}>
                  ♥
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "60px 20px", background: "#fff", border: "1px dashed var(--color-border-neutral)", borderRadius: "var(--radius-card)" }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>♡</div>
          <h3 style={{ fontFamily: "var(--font-display)", fontSize: 15, margin: "0 0 6px" }}>No saved exams yet</h3>
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: "0 0 16px" }}>Tap the heart icon on any exam card to save it here.</p>
          <Link to="/" style={{ display: "inline-block", background: "var(--color-navy-primary)", color: "#fff", borderRadius: "var(--radius-btn)", padding: "10px 20px", fontSize: 13, fontWeight: 700, textDecoration: "none" }}>
            Browse exams
          </Link>
        </div>
      )}
    </div>
  );
}
