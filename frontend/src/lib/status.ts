// Status vocabulary reconciled from two sources: the discovery redesign's
// set (open/closing_soon/closed/result/admit_card) and what real exam rows
// actually carry (interview_scheduled, postponed, result_declared -- see
// the old frontend's STATUS_DISPLAY). Covers both rather than picking one.

export interface StatusMeta {
  label: string;
  bg: string;
  text: string;
}

const STATUS_META: Record<string, StatusMeta> = {
  open: { label: "Open", bg: "var(--status-open-bg)", text: "var(--status-open-text)" },
  closing_soon: { label: "Closing Soon", bg: "var(--status-closing-soon-bg)", text: "var(--status-closing-soon-text)" },
  closed: { label: "Closed", bg: "var(--status-closed-bg)", text: "var(--status-closed-text)" },
  result: { label: "Result Declared", bg: "var(--status-result-bg)", text: "var(--status-result-text)" },
  result_declared: { label: "Result Declared", bg: "var(--status-result-bg)", text: "var(--status-result-text)" },
  admit_card: { label: "Admit Card Out", bg: "var(--status-admit-card-bg)", text: "var(--status-admit-card-text)" },
  interview_scheduled: { label: "Interview Scheduled", bg: "var(--status-interview-bg)", text: "var(--status-interview-text)" },
  postponed: { label: "Postponed", bg: "var(--status-closing-soon-bg)", text: "var(--status-closing-soon-text)" },
};

export function statusMeta(status: string | null): StatusMeta {
  if (status && STATUS_META[status]) return STATUS_META[status];
  return { label: status ?? "Unknown", bg: "var(--color-bg-warm-neutral)", text: "var(--color-text-secondary)" };
}
