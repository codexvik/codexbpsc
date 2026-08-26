import { useState } from "react";
import { api } from "../api/client";

const DEGREE_OPTIONS = ["10th Pass", "12th Pass", "B.A.", "B.Sc.", "B.Com.", "B.Tech.", "Graduate", "Post Graduate"];
const CATEGORY_OPTIONS = ["General", "OBC", "EWS", "SC", "ST"];

export default function EligibilityChecker({ examId }: { examId: number }) {
  const [degree, setDegree] = useState("");
  const [age, setAge] = useState("");
  const [category, setCategory] = useState("General");
  const [result, setResult] = useState<{ eligible: boolean | null; reason: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const resp = await api.checkEligibility(examId, degree, Number(age), category);
      setResult({ eligible: resp.eligible, reason: resp.reason });
    } catch {
      setResult({ eligible: null, reason: "Couldn't check right now, please try again." });
    } finally {
      setSubmitting(false);
    }
  }

  const verdictColor = result?.eligible === true ? "var(--status-open-text)" : result?.eligible === false ? "var(--color-orange-text)" : "var(--color-text-secondary)";
  const verdictBg = result?.eligible === true ? "var(--status-open-bg)" : result?.eligible === false ? "var(--status-closing-soon-bg)" : "var(--color-bg-warm-neutral)";

  return (
    <div style={{ background: "#fff", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-card)", padding: 20 }}>
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: 14.5, fontWeight: 800, margin: "0 0 14px" }}>Check Your Eligibility</h3>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          Highest qualification
          <input list="degree-options" required value={degree} onChange={(e) => setDegree(e.target.value)} placeholder="e.g. B.A., B.Sc." style={inputStyle} />
          <datalist id="degree-options">
            {DEGREE_OPTIONS.map((d) => (
              <option key={d} value={d} />
            ))}
          </datalist>
        </label>
        <label style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          Age
          <input type="number" required min={0} max={100} value={age} onChange={(e) => setAge(e.target.value)} style={inputStyle} />
        </label>
        <label style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={inputStyle}>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: 0 }}>Certificate requirements for your category will be shown here once available.</p>
        <button type="submit" disabled={submitting} style={{ alignSelf: "flex-start", padding: "10px 20px", border: "none", borderRadius: "var(--radius-btn)", background: "var(--color-navy-primary)", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
          Check Eligibility
        </button>
      </form>
      {result && (
        <div style={{ marginTop: 14, padding: "12px 14px", borderRadius: 8, fontWeight: 600, color: verdictColor, background: verdictBg }}>
          {result.eligible === true ? "✓ You are eligible. " : result.eligible === false ? "✗ You are not eligible. " : ""}
          {result.reason}
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  marginTop: 4,
  padding: "10px 12px",
  border: "1px solid var(--color-border-neutral)",
  borderRadius: "var(--radius-input)",
  fontSize: 14,
  fontFamily: "var(--font-body)",
};
