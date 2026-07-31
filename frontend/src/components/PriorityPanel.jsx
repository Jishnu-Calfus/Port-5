function severityClass(severity) {
  return severity.toLowerCase().replace(/\s+/g, "-");
}

export default function PriorityPanel({ data }) {
  return (
    <div className="card">
      <div className="section-title">Top Priority Actions</div>
      <div className="priority-list">
        {data.map((row) => (
          <div className="priority-row" key={row.category}>
            <span className={`severity-badge ${severityClass(row.severity)}`}>
              {row.severity}
            </span>
            <span className="priority-name">{row.category}</span>
            <span className="priority-detail">
              {row.volume} items &middot; {(row.share_negative * 100).toFixed(0)}% negative &middot; score {row.score}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
