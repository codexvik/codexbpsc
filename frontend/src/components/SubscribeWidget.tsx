import { useState } from "react";
import { api } from "../api/client";

export default function SubscribeWidget({ examId }: { examId: number }) {
  const [phone, setPhone] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onAction(action: "subscribe" | "unsubscribe") {
    setBusy(true);
    try {
      if (action === "subscribe") {
        await api.subscribe(phone, examId);
        // No overclaiming: WhatsApp delivery isn't built yet (docs/backlog.md).
        // Telegram is real and works via the bot's /subscribe command.
        setResult("✓ Subscribed. For instant alerts today, use our Telegram bot -- WhatsApp delivery is on the way.");
      } else {
        await api.unsubscribe(phone, examId);
        setResult("Unsubscribed.");
      }
    } catch (err) {
      setResult(err instanceof Error ? err.message : "Something went wrong, please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ background: "#fff", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-card)", padding: 20 }}>
      <h3 style={{ fontFamily: "var(--font-display)", fontSize: 14.5, fontWeight: 800, margin: "0 0 14px" }}>Get Alerts</h3>
      <label style={{ fontSize: 13, color: "var(--color-text-secondary)", display: "block", marginBottom: 12 }}>
        Phone number
        <input
          type="tel"
          required
          minLength={8}
          maxLength={20}
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+91XXXXXXXXXX"
          style={{ display: "block", width: "100%", marginTop: 4, padding: "10px 12px", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-input)", fontSize: 14 }}
        />
      </label>
      <div style={{ display: "flex", gap: 10 }}>
        <button
          type="button"
          disabled={busy || !phone}
          onClick={() => onAction("subscribe")}
          style={{ padding: "10px 20px", border: "none", borderRadius: "var(--radius-btn)", background: "var(--color-navy-primary)", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}
        >
          Subscribe
        </button>
        <button
          type="button"
          disabled={busy || !phone}
          onClick={() => onAction("unsubscribe")}
          style={{ padding: "10px 20px", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-btn)", background: "none", color: "var(--color-text-default)", fontWeight: 700, fontSize: 14, cursor: "pointer" }}
        >
          Unsubscribe
        </button>
      </div>
      {result && <p style={{ marginTop: 12, fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)" }}>{result}</p>}
    </div>
  );
}
