import { useEffect, useState } from "react";
import * as api from "./api";
import StatTile from "./components/StatTile";
import PriorityPanel from "./components/PriorityPanel";
import CategoryBarChart from "./components/CategoryBarChart";
import SentimentDivergingBar from "./components/SentimentDivergingBar";
import SourceDonut from "./components/SourceDonut";
import TrendLine from "./components/TrendLine";
import AskFeedback from "./components/AskFeedback";
import DataAgent from "./components/DataAgent";
import OverviewSummary from "./components/OverviewSummary";

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState("all");

  useEffect(() => {
    Promise.all([
      api.getKpis(),
      api.getPriority(),
      api.getCategories(),
      api.getSentiment(),
      api.getSources(),
      api.getTrend(),
      api.getSummary(),
      api.getCurrentWeek(),
    ])
      .then(([kpis, priority, categories, sentiment, sources, trend, summary, currentWeek]) => {
        setData({ kpis, priority, categories, sentiment, sources, trend, summary, currentWeek });
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="app">
        <p className="error">Failed to load dashboard: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="app">
        <p className="loading">Loading dashboard...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>PulseAI</h1>
        <p>Consumer fintech feedback insights</p>
      </header>

      <div className="view-tabs">
        <button className={view === "all" ? "view-tab active" : "view-tab"} onClick={() => setView("all")}>
          All time
        </button>
        <button className={view === "week" ? "view-tab active" : "view-tab"} onClick={() => setView("week")}>
          This week
        </button>
        {view === "week" && (
          <span className="view-tab-range">
            {data.currentWeek.week_start} – {data.currentWeek.week_end}
          </span>
        )}
      </div>

      {view === "all" ? (
        <>
          <div className="kpi-row">
            <StatTile label="Total Feedback" value={data.kpis.total_feedback} />
            <StatTile label="Negative Sentiment" value={`${data.kpis.negative_pct}%`} />
            <StatTile label="Most Active Category" value={data.kpis.top_category} />
            <StatTile label="Critical Open Issues" value={data.kpis.critical_open_issues} />
          </div>
          <div className="charts-grid">
            <CategoryBarChart data={data.categories} />
            <SentimentDivergingBar data={data.sentiment} />
            <SourceDonut data={data.sources} />
            <TrendLine data={data.trend} />
          </div>
          <OverviewSummary summary={data.summary.summary} />
        </>
      ) : (
        <>
          <div className="kpi-row">
            <StatTile label="Total Feedback" value={data.currentWeek.kpis.total_feedback} />
            <StatTile label="Negative Sentiment" value={`${data.currentWeek.kpis.negative_pct}%`} />
            <StatTile label="Most Active Category" value={data.currentWeek.kpis.top_category} />
            <StatTile label="Critical Open Issues" value={data.currentWeek.kpis.critical_open_issues} />
          </div>
          <div className="charts-grid">
            <CategoryBarChart data={data.currentWeek.categories} />
            <SentimentDivergingBar data={data.currentWeek.sentiment} />
            <SourceDonut data={data.currentWeek.sources} />
            <TrendLine data={data.currentWeek.trend} />
          </div>
        </>
      )}

      <PriorityPanel data={data.priority} />

      <AskFeedback />

      <DataAgent />
    </div>
  );
}

export default App;
