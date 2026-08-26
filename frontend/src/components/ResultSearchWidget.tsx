import { useState } from "react";
import { api } from "../api/client";

export default function ResultSearchWidget({ examId }: { examId: number }) {
  const [rollNumber, setRollNumber] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const resp = await api.searchResult(examId, rollNumber);
      if (!resp.found) {
        setResult("No result found for this roll number.");
      } else {
        setResult(`Status: ${resp.status ?? "—"}${resp.rank ? ` · Rank: ${resp.rank}` : ""}`);
      }
    } catch {
      setResult("Couldn't search right now, please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-card)", padding: 20 }}>
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: 14.5, fontWeight: 800, margin: "0 0 14px" }}>Search Your Result</h3>
      <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label style={{ fontSize: 13, color: "var(--color-text-secondary)" }}>
          Roll number
          <input
            required
            value={rollNumber}
            onChange={(e) => setRollNumber(e.target.value)}
            placeholder="e.g. 4021178"
            style={{ display: "block", width: "100%", marginTop: 4, padding: "10px 12px", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-input)", fontSize: 14 }}
          />
        </label>
        <button type="submit" disabled={busy} style={{ alignSelf: "flex-start", padding: "10px 20px", border: "none", borderRadius: "var(--radius-btn)", background: "var(--color-navy-primary)", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
          Search
        </button>
      </form>
      {result && <p style={{ marginTop: 12, fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)" }}>{result}</p>}
    </div>
  );
}
