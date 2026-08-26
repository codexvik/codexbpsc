import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ExamDetail as ExamDetailType } from "../api/types";
import CallbackBar from "../components/CallbackBar";
import EligibilityChecker from "../components/EligibilityChecker";
import NoticeFeed from "../components/NoticeFeed";
import ResultSearchWidget from "../components/ResultSearchWidget";
import SubscribeWidget from "../components/SubscribeWidget";
import { categoryAccent } from "../lib/category";
import { fmtDate, fmtNum } from "../lib/dates";
import { useAppliedExams, useSavedExams } from "../lib/savedStorage";
import { statusMeta } from "../lib/status";

const MOBILE_BREAKPOINT = 759;

const cardStyle: React.CSSProperties = {
  background: "#fff",
  border: "1px solid var(--color-border-neutral)",
  borderRadius: "var(--radius-card)",
  padding: 20,
  marginTop: 18,
};
const cardHeading: React.CSSProperties = { fontFamily: "var(--font-display)", fontSize: 14.5, fontWeight: 800, margin: "0 0 14px" };

export default function ExamDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [exam, setExam] = useState<ExamDetailType | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [width, setWidth] = useState(window.innerWidth);
  const { has: isSaved, toggle: toggleSave } = useSavedExams();
  const { has: isApplied, toggle: toggleApplied } = useAppliedExams();

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const isMobile = width <= MOBILE_BREAKPOINT;

  useEffect(() => {
    if (!id) return;
    api
      .getExam(Number(id))
      .then(setExam)
      .catch(() => setNotFound(true));
  }, [id]);

  if (notFound) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <p>Exam not found.</p>
        <Link to="/">← Back to search</Link>
      </div>
    );
  }
  if (!exam) return <div style={{ padding: 40, textAlign: "center", color: "var(--color-text-muted)" }}>Loading…</div>;

  const status = statusMeta(exam.status);
  const [c1, c2] = categoryAccent(exam.board_category);
  const saved = isSaved(exam.id);
  const applied = isApplied(exam.id);

  const timelineEntries = exam.key_dates_json ? Object.entries(exam.key_dates_json) : [];
  const today = new Date();

  return (
    <div>
      <div style={{ maxWidth: "var(--maxw-detail)", margin: "0 auto", padding: isMobile ? "16px 16px 0" : "20px 32px 0" }}>
        <button type="button" onClick={() => navigate(-1)} style={{ background: "none", border: "none", color: "var(--color-text-secondary)", fontSize: 13, fontWeight: 700, cursor: "pointer", padding: 0 }}>
          ← Back to search
        </button>
      </div>

      <div style={{ maxWidth: "var(--maxw-detail)", margin: "12px auto 0", padding: isMobile ? "0 16px" : "0 32px" }}>
        <div style={{ borderRadius: "var(--radius-card-lg)", overflow: "hidden", background: `linear-gradient(135deg, ${c1}, ${c2})`, padding: isMobile ? "22px 20px" : "30px 32px", color: "#fff" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
            <div>
              <div style={{ display: "inline-flex", alignItems: "center", background: "rgba(255,255,255,.2)", color: "#fff", fontSize: 11.5, fontWeight: 700, padding: "5px 11px", borderRadius: "var(--radius-pill)" }}>
                {status.label}
              </div>
              <h1 style={{ fontFamily: "var(--font-display)", fontSize: isMobile ? 20 : 25, fontWeight: 800, margin: "10px 0 4px", lineHeight: 1.25 }}>{exam.name}</h1>
              <p style={{ fontSize: 13, color: "rgba(255,255,255,.85)", margin: 0 }}>{exam.board_name}</p>
              {exam.board_name_hindi && <p style={{ fontSize: 12, color: "rgba(255,255,255,.7)", margin: "2px 0 0" }}>{exam.board_name_hindi}</p>}
              <div style={{ display: "flex", gap: 8, marginTop: 14, alignItems: "center", flexWrap: "wrap" }}>
                {exam.advt_no && (
                  <div style={{ background: "rgba(255,255,255,.15)", borderRadius: 8, padding: "5px 10px", fontSize: 12.5, fontWeight: 700 }}>Advt. {exam.advt_no}</div>
                )}
                {exam.verified && (
                  <div style={{ display: "flex", alignItems: "center", gap: 4, background: "rgba(255,255,255,.15)", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700 }}>
                    ✓ Verified
                  </div>
                )}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "row", gap: 8, width: isMobile ? "100%" : "auto" }}>
              <button
                type="button"
                onClick={() => toggleSave(exam.id)}
                style={{ flex: 1, background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.3)", color: "#fff", borderRadius: "var(--radius-btn-lg)", padding: "11px 14px", fontSize: 12.5, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" }}
              >
                {saved ? "♥ Saved" : "♡ Save"}
              </button>
              <button
                type="button"
                onClick={() => toggleApplied(exam.id)}
                style={{ flex: 1, background: "var(--color-orange-accent)", border: "none", color: "#fff", borderRadius: "var(--radius-btn-lg)", padding: "11px 14px", fontSize: 12.5, fontWeight: 800, cursor: "pointer", whiteSpace: "nowrap" }}
              >
                {applied ? "✓ Applied" : "Mark Applied"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: "var(--maxw-detail)", margin: "0 auto", padding: isMobile ? "18px 16px 60px" : "22px 32px 70px", display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1.7fr 300px", gap: "var(--gap-detail-body)" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          <EligibilityChecker examId={exam.id} />

          {exam.eligibility_json?.required_degree && (
            <div style={cardStyle}>
              <h3 style={cardHeading}>Eligibility Criteria</h3>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--color-text-default)", lineHeight: 1.8 }}>
                <li>Required qualification: {exam.eligibility_json.required_degree.join(", ")}</li>
                {exam.eligibility_json.min_age != null && <li>Minimum age: {exam.eligibility_json.min_age}</li>}
                {exam.eligibility_json.max_age != null && <li>Maximum age: {exam.eligibility_json.max_age} (with category relaxation)</li>}
              </ul>
            </div>
          )}

          {timelineEntries.length > 0 && (
            <div style={cardStyle}>
              <h3 style={cardHeading}>Important Dates Timeline</h3>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {timelineEntries.map(([label, value], i) => {
                  const past = new Date(value) <= today;
                  return (
                    <div key={label} style={{ display: "flex", gap: 12 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                        <div style={{ width: 10, height: 10, borderRadius: "50%", background: past ? c1 : "var(--color-border-neutral)", flexShrink: 0, marginTop: 3 }} />
                        {i < timelineEntries.length - 1 && <div style={{ width: 2, flex: 1, background: "var(--color-border-neutral)", marginTop: 2 }} />}
                      </div>
                      <div style={{ paddingBottom: 18 }}>
                        <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--color-navy-dark)", textTransform: "capitalize" }}>{label.replace(/_/g, " ")}</div>
                        <div style={{ fontSize: 11.5, color: "var(--color-text-muted)" }}>{fmtDate(value)}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div style={cardStyle}>
            <SubscribeWidget examId={exam.id} />
          </div>

          <div style={cardStyle}>
            <h3 style={cardHeading}>Notice Feed</h3>
            <NoticeFeed notices={exam.notices} />
          </div>

          <div style={cardStyle}>
            <ResultSearchWidget examId={exam.id} />
          </div>

          {exam.official_website && (
            <div style={{ ...cardStyle, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <a href={exam.official_website} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", background: "#fff", border: "1px solid var(--color-border-neutral)", color: "var(--color-navy-dark)", borderRadius: "var(--radius-btn)", padding: "10px 16px", fontSize: 12.5, fontWeight: 700 }}>
                🔗 Official Website
              </a>
            </div>
          )}
        </div>

        <div style={isMobile ? {} : { position: "sticky", top: 150, alignSelf: "start" }}>
          <div style={{ background: "#fff", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-card)", padding: 18 }}>
            <h4 style={{ fontFamily: "var(--font-display)", fontSize: 12, fontWeight: 800, margin: "0 0 12px", color: "var(--color-text-muted)", letterSpacing: ".03em" }}>QUICK FACTS</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              <FactRow k="Vacancies" v={fmtNum(exam.vacancy_count)} />
              {exam.next_key_date_value && <FactRow k={exam.next_key_date_label ?? "Next date"} v={fmtDate(exam.next_key_date_value)} bold />}
              <FactRow k="Category" v={exam.board_category ?? "—"} />
            </div>
          </div>

          <div style={{ marginTop: 18, padding: 16, textAlign: "center", border: "1px dashed var(--color-border-neutral)", borderRadius: "var(--radius-card)", fontSize: 12.5, color: "var(--color-text-muted)" }}>
            Partner Space · Reserved — not active yet
          </div>
        </div>
      </div>

      <CallbackBar examId={exam.id} />
    </div>
  );
}

function FactRow({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
      <span style={{ color: "var(--color-text-muted)", textTransform: "capitalize" }}>{k}</span>
      <span style={{ fontWeight: bold ? 800 : 700 }}>{v}</span>
    </div>
  );
}
