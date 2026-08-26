// Saved/Applied tracking, client-side only -- there's no login system
// (Phase 0 explicitly excludes one), so this is per-device via
// localStorage, not per-account. The design handoff's own README notes
// this is "local-only in the prototype, persisted per user in production" --
// production here just means "no accounts exist yet", so local-only is the
// real, honest behavior for now, not a placeholder.

import { useCallback, useEffect, useState } from "react";

const SAVED_KEY = "codexbpsc:savedExamIds";
const APPLIED_KEY = "codexbpsc:appliedExamIds";

function readSet(key: string): Set<number> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw));
  } catch {
    return new Set();
  }
}

function writeSet(key: string, set: Set<number>) {
  localStorage.setItem(key, JSON.stringify(Array.from(set)));
}

function useIdSet(key: string) {
  const [ids, setIds] = useState<Set<number>>(() => readSet(key));

  useEffect(() => {
    writeSet(key, ids);
  }, [key, ids]);

  const toggle = useCallback((id: number) => {
    setIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const has = useCallback((id: number) => ids.has(id), [ids]);

  return { ids, has, toggle };
}

export function useSavedExams() {
  return useIdSet(SAVED_KEY);
}

export function useAppliedExams() {
  return useIdSet(APPLIED_KEY);
}
