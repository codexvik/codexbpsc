export default function SkeletonGrid({ gridCols }: { gridCols: string }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: gridCols, gap: "var(--gap-card-grid)" }}>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} style={{ borderRadius: "var(--radius-card)", overflow: "hidden", background: "#fff", border: "1px solid var(--color-border-neutral)" }}>
          <div className="skel" style={{ height: 130, width: "100%" }} />
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            <div className="skel" style={{ height: 14, width: "70%", borderRadius: 4 }} />
            <div className="skel" style={{ height: 11, width: "50%", borderRadius: 4 }} />
            <div className="skel" style={{ height: 11, width: "90%", borderRadius: 4, marginTop: 6 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
