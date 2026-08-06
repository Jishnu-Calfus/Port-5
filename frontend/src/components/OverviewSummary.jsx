export default function OverviewSummary({ summary }) {
  return (
    <div className="card summary-card">
      <div className="section-title">Overview</div>
      <p>{summary}</p>
    </div>
  );
}
