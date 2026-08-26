import { useState } from "react";
import { api } from "../api/client";

export default function CallbackBar({ examId }: { examId?: number }) {
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.requestCallback(phone, examId ?? null);
      setResult("Thanks -- we'll call you back soon.");
      setOpen(false);
      setPhone("");
    } catch {
      setResult("Couldn't submit right now, please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ position: "sticky", bottom: 0, zIndex: 30, background: "#fff", borderTop: "1px solid var(--color-border-neutral)", padding: "12px 16px calc(12px + env(safe-area-inset-bottom))" }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            width: "100%",
            padding: 13,
            border: "none",
            borderRadius: "var(--radius-btn-lg)",
            background: "var(--color-navy-dark)",
            color: "#fff",
            fontWeight: 700,
            fontSize: 14.5,
            cursor: "pointer",
          }}
        >
          📞 Request a Callback
        </button>
        {open && (
          <form onSubmit={onSubmit} style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <input
              type="tel"
              required
              minLength={8}
              maxLength={20}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91XXXXXXXXXX"
              style={{ flex: 1, padding: "11px 13px", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-btn-lg)", fontSize: 14.5 }}
            />
            <button
              type="submit"
              disabled={submitting}
              style={{ padding: "11px 20px", border: "none", borderRadius: "var(--radius-btn-lg)", background: "var(--color-navy-primary)", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}
            >
              Submit
            </button>
          </form>
        )}
        {result && <p style={{ marginTop: 8, fontSize: 13, fontWeight: 600, textAlign: "center", color: "var(--color-text-secondary)" }}>{result}</p>}
      </div>
    </div>
  );
}
