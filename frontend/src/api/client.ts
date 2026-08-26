import type {
  AlertItem,
  CallbackRequestResponse,
  EligibilityCheckResponse,
  ExamDetail,
  ExamSummary,
  ResultSearchResponse,
  SubscribeResponse,
} from "./types";

// Default matches `uvicorn api.main:app --reload`'s default port (8000) --
// verified 2026-08-25 that this had drifted to a stale 8123, a leftover
// dev server nobody was restarting, silently serving days-old data.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  listExams: () => request<ExamSummary[]>("/exams"),
  getExam: (id: number) => request<ExamDetail>(`/exams/${id}`),
  recentNotices: (limit = 10) => request<AlertItem[]>(`/notices/recent?limit=${limit}`),

  subscribe: (phone_number: string, exam_id: number) =>
    request<SubscribeResponse>("/subscribe", {
      method: "POST",
      body: JSON.stringify({ phone_number, exam_id }),
    }),
  unsubscribe: (phone_number: string, exam_id: number) =>
    request<SubscribeResponse>("/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ phone_number, exam_id }),
    }),

  checkEligibility: (exam_id: number, degree: string, age: number, category: string) =>
    request<EligibilityCheckResponse>("/eligibility-check", {
      method: "POST",
      body: JSON.stringify({ exam_id, degree, age, category }),
    }),

  searchResult: (exam_id: number, roll_number: string) =>
    request<ResultSearchResponse>(
      `/results?exam_id=${encodeURIComponent(exam_id)}&roll_number=${encodeURIComponent(roll_number)}`
    ),

  requestCallback: (phone_number: string, exam_id: number | null) =>
    request<CallbackRequestResponse>("/callback-request", {
      method: "POST",
      body: JSON.stringify({ phone_number, exam_id }),
    }),

  myAlerts: (phone_number: string) =>
    request<AlertItem[]>(`/my-alerts?phone_number=${encodeURIComponent(phone_number)}`),
};
