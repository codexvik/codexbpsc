import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useSavedExams } from "../lib/savedStorage";

const MOBILE_BREAKPOINT = 759;

export default function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { ids: savedIds } = useSavedExams();

  const [width, setWidth] = useState(window.innerWidth);
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const isMobile = width <= MOBILE_BREAKPOINT;

  const [searchValue, setSearchValue] = useState(searchParams.get("q") ?? "");
  useEffect(() => {
    setSearchValue(searchParams.get("q") ?? "");
  }, [searchParams]);

  function onSearchChange(value: string) {
    setSearchValue(value);
    const params = new URLSearchParams(location.pathname === "/" ? searchParams : undefined);
    if (value) params.set("q", value);
    else params.delete("q");
    navigate({ pathname: "/", search: params.toString() });
  }

  const searchBox = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        background: "var(--color-bg-warm-neutral)",
        border: "1px solid var(--color-border-neutral)",
        borderRadius: "var(--radius-input)",
        padding: isMobile ? "9px 14px" : "8px 14px",
        width: "100%",
      }}
    >
      <span style={{ fontSize: 13, opacity: 0.5 }}>🔍</span>
      <input
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={isMobile ? "Search exam, department..." : "Search exam, department, state..."}
        style={{
          border: "none",
          background: "transparent",
          outline: "none",
          fontSize: isMobile ? 13.5 : 13,
          width: "100%",
          color: "var(--color-navy-dark)",
        }}
      />
    </div>
  );

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "#fff",
        borderBottom: "1px solid var(--color-border-neutral)",
        padding: isMobile ? "10px 14px" : "12px 32px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 9,
              background: "linear-gradient(135deg, var(--color-navy-primary), var(--color-navy-hero-end))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontFamily: "var(--font-display)",
              fontWeight: 800,
              fontSize: 15,
              flexShrink: 0,
            }}
          >
            S
          </div>
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 16, color: "var(--color-navy-dark)" }}>
              SarkariExams
            </span>
            <span style={{ fontSize: 10.5, color: "var(--color-text-muted)", fontWeight: 600 }}>परीक्षा खोज · Bihar</span>
          </div>
        </Link>

        {!isMobile && <div style={{ flex: 1, display: "flex", justifyContent: "center", padding: "0 20px", maxWidth: 420 }}>{searchBox}</div>}

        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          {!isMobile && (
            <Link
              to="/"
              style={{
                background: location.pathname === "/" ? "var(--color-bg-warm-neutral)" : "none",
                border: "none",
                borderRadius: "var(--radius-btn)",
                padding: "9px 13px",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--color-navy-dark)",
                textDecoration: "none",
              }}
            >
              Discover
            </Link>
          )}
          <Link
            to="/saved"
            style={{
              background: location.pathname === "/saved" ? "var(--color-bg-warm-neutral)" : "none",
              border: "none",
              borderRadius: "var(--radius-btn)",
              padding: "9px 12px",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--color-navy-dark)",
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            ♥{!isMobile && <span>&nbsp;Saved</span>}
            {savedIds.size > 0 && (
              <span
                style={{
                  background: "var(--color-orange-accent)",
                  color: "#fff",
                  fontSize: 10,
                  fontWeight: 800,
                  borderRadius: 10,
                  padding: "1px 6px",
                }}
              >
                {savedIds.size}
              </span>
            )}
          </Link>
          {!isMobile && (
            <button
              type="button"
              title="Not built yet -- Phase 0 has no login system"
              style={{
                background: "var(--color-navy-primary)",
                color: "#fff",
                border: "none",
                borderRadius: "var(--radius-btn)",
                padding: "10px 16px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "not-allowed",
                marginLeft: 2,
                opacity: 0.6,
              }}
            >
              Sign in
            </button>
          )}
        </div>
      </div>
      {isMobile && searchBox}
    </div>
  );
}
