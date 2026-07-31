export default function WeeklySummary({ summary }) {
  return (
    <div className="card summary-card">
      <div className="section-title">Weekly Summary</div>
      <p>{summary}</p>
    </div>
  );
}
