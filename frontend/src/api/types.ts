// Mirrors api/schemas.py exactly -- keep these two in sync by hand; there's
// no shared codegen yet (would be a reasonable later addition once the
// schema stabilizes).

export interface ExamSummary {
  id: number;
  name: string;
  advt_no: string | null;
  category: string | null;
  vacancy_count: number | null;
  status: string | null;
  latest_change_snippet: string | null;
  notice_count: number;
  board_category: string | null;
  board_monogram: string | null;
  verified: boolean;
  next_key_date_label: string | null;
  next_key_date_value: string | null;
}

export interface NoticeOut {
  id: number;
  exam_id: number;
  source_url: string;
  change_type: string;
  summary_plain_language: string | null;
  old_value: string | null;
  new_value: string | null;
  effective_date: string | null;
  confidence: string | null;
  archive_url: string | null;
  detected_at: string;
}

export interface EligibilityJson {
  required_degree?: string[];
  min_age?: number;
  max_age?: number;
  category_age_relaxation?: Record<string, number>;
}

export interface ExamDetail extends ExamSummary {
  eligibility_json: EligibilityJson | null;
  key_dates_json: Record<string, string> | null;
  notices: NoticeOut[];
  board_name: string | null;
  board_name_hindi: string | null;
  official_website: string | null;
}

export interface SubscribeResponse {
  exam_id: number;
  phone_number: string;
  active: boolean;
}

export interface EligibilityCheckResponse {
  exam_id: number;
  eligible: boolean | null;
  reason: string;
}

export interface ResultSearchResponse {
  found: boolean;
  roll_number: string;
  status: string | null;
  rank: number | null;
  source_notice_url: string | null;
}

export interface CallbackRequestResponse {
  id: number;
  phone_number: string;
  exam_id: number | null;
}

export interface AlertItem {
  id: number;
  exam_id: number;
  exam_name: string;
  source_url: string;
  change_type: string;
  summary_plain_language: string | null;
  effective_date: string | null;
  confidence: string | null;
  archive_url: string | null;
  detected_at: string;
}
