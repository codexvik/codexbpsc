// Board categories shown in the filter bar. All five are real categories a
// board can genuinely belong to (matches source_config.py's board_category
// field) -- only "State PSC" has a populated source today (bpsc_bihar), so
// the others just return zero results until a second source is onboarded.
// That's an honest empty state, not a fake category.

export interface CategoryDef {
  key: string;
  icon: string;
  label: string;
  accent: [string, string];
}

export const CATEGORIES: CategoryDef[] = [
  { key: "All", icon: "🔎", label: "All", accent: ["var(--color-navy-primary)", "var(--color-navy-hero-end)"] },
  { key: "State PSC", icon: "🏛️", label: "State PSC", accent: ["var(--accent-state-psc-1)", "var(--accent-state-psc-2)"] },
  { key: "SSC", icon: "📝", label: "SSC", accent: ["var(--accent-ssc-1)", "var(--accent-ssc-2)"] },
  { key: "Railway", icon: "🚆", label: "Railway", accent: ["var(--accent-railway-1)", "var(--accent-railway-2)"] },
  { key: "Police", icon: "🛡️", label: "Police", accent: ["var(--accent-police-1)", "var(--accent-police-2)"] },
  { key: "Teaching", icon: "🎓", label: "Teaching", accent: ["var(--accent-teaching-1)", "var(--accent-teaching-2)"] },
];

export function categoryAccent(category: string | null): [string, string] {
  const found = CATEGORIES.find((c) => c.key === category);
  return found?.accent ?? ["var(--color-text-muted)", "var(--color-text-secondary)"];
}
