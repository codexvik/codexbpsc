import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { ExamSummary } from "../api/types";
import CallbackBar from "../components/CallbackBar";
import ExamCard from "../components/ExamCard";
import FilterBar from "../components/FilterBar";
import NotificationsStrip from "../components/NotificationsStrip";
import SkeletonGrid from "../components/SkeletonGrid";

const MOBILE_BREAKPOINT = 759;

export default function Home() {
  const [params] = useSearchParams();
  const [width, setWidth] = useState(window.innerWidth);
  const [exams, setExams] = useState<ExamSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const isMobile = width <= MOBILE_BREAKPOINT;

  function load() {
    api
      .listExams()
      .then((data) => {
        setExams(data);
        setError(null);
      })
      .catch(() => setError("Couldn't load exams right now. Please try again shortly."));
  }

  useEffect(load, []);

  function refresh() {
    setRefreshing(true);
    load();
    setTimeout(() => setRefreshing(false), 500);
  }

  const q = (params.get("q") ?? "").trim().toLowerCase();
  const category = params.get("category") ?? "All";
  const qual = params.get("qual") ?? "All";
  const status = params.get("status") ?? "All";

  const filtered = (exams ?? []).filter((ex) => {
    if (q && !(ex.name.toLowerCase().includes(q) || (ex.advt_no ?? "").toLowerCase().includes(q) || (ex.board_category ?? "").toLowerCase().includes(q))) {
      return false;
    }
    if (category !== "All" && ex.board_category !== category) return false;
    // qualificationBucket isn't in our schema yet (no exam has eligibility_json
    // populated) -- the qualification filter is wired but has nothing to
    // match against today, so it never excludes a real exam until that data exists.
    void qual;
    if (status !== "All" && ex.status !== status) return false;
    return true;
  });

  const gridCols = isMobile ? "1fr" : "repeat(3,1fr)";
  const loading = exams === null && !error;

  return (
    <div>
      <div
        style={{
          background: "linear-gradient(160deg, var(--color-navy-hero-start) 0%, var(--color-navy-hero-mid) 55%, var(--color-navy-hero-end) 100%)",
          padding: isMobile ? "32px 20px 24px" : "48px 32px 32px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ position: "absolute", top: -60, right: -40, width: 280, height: 280, borderRadius: "50%", background: "radial-gradient(circle, rgba(255,153,51,.18), transparent 70%)" }} />
        <div style={{ maxWidth: 680, margin: "0 auto", textAlign: "center", position: "relative", zIndex: 1 }}>
          <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: isMobile ? 25 : 36, color: "#fff", margin: "0 0 6px", letterSpacing: "-.01em", lineHeight: 1.2 }}>
            Find your next government exam
          </h1>
          <p style={{ fontSize: isMobile ? 13 : 15, color: "#c8d3e8", margin: 0 }}>
            Bihar exams today, built for all of India — verified dates, no confusion.
          </p>
        </div>
      </div>

      <NotificationsStrip isMobile={isMobile} />
      <FilterBar isMobile={isMobile} sticky />

      <div style={{ maxWidth: "var(--maxw-home)", margin: "0 auto", padding: isMobile ? "18px 14px 6px" : "22px 32px 6px", display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: isMobile ? 16 : 19, fontWeight: 800, margin: 0 }}>
          {loading ? "…" : `${filtered.length} exam${filtered.length === 1 ? "" : "s"} found`}
        </h2>
        <button
          type="button"
          onClick={refresh}
          style={{ background: "var(--color-bg-warm-neutral)", border: "1px solid var(--color-border-neutral)", borderRadius: "var(--radius-btn)", padding: "7px 12px", fontSize: 12, fontWeight: 700, color: "var(--color-text-secondary)", cursor: "pointer", flexShrink: 0 }}
        >
          ↻ Refresh
        </button>
      </div>

      <div style={{ maxWidth: "var(--maxw-home)", margin: "0 auto", padding: isMobile ? "10px 14px 50px" : "12px 32px 60px" }}>
        {error && <p style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "30px 0" }}>{error}</p>}

        {(loading || refreshing) && !error && <SkeletonGrid gridCols={gridCols} />}

        {!loading && !refreshing && !error && filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: "60px 20px" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🗂️</div>
            <h3 style={{ fontFamily: "var(--font-display)", fontSize: 17, margin: "0 0 6px" }}>No exams match these filters</h3>
            <p style={{ fontSize: 13, color: "var(--color-text-muted)", margin: "0 0 16px" }}>Try clearing a filter or searching something else.</p>
          </div>
        )}

        {!loading && !refreshing && !error && filtered.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: gridCols, gap: "var(--gap-card-grid)" }}>
            {filtered.map((ex) => (
              <ExamCard key={ex.id} exam={ex} />
            ))}
          </div>
        )}
      </div>

      <CallbackBar />
    </div>
  );
}
