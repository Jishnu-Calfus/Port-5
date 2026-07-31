import { useEffect, useState } from "react";
import * as api from "./api";
import StatTile from "./components/StatTile";
import PriorityPanel from "./components/PriorityPanel";
import CategoryBarChart from "./components/CategoryBarChart";
import SentimentDivergingBar from "./components/SentimentDivergingBar";
import SourceDonut from "./components/SourceDonut";
import TrendLine from "./components/TrendLine";
import AskFeedback from "./components/AskFeedback";
import WeeklySummary from "./components/WeeklySummary";

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api.getKpis(),
      api.getPriority(),
      api.getCategories(),
      api.getSentiment(),
      api.getSources(),
      api.getTrend(),
      api.getSummary(),
    ])
      .then(([kpis, priority, categories, sentiment, sources, trend, summary]) => {
        setData({ kpis, priority, categories, sentiment, sources, trend, summary });
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

      <div className="kpi-row">
        <StatTile label="Total Feedback" value={data.kpis.total_feedback} />
        <StatTile label="Negative Sentiment" value={`${data.kpis.negative_pct}%`} />
        <StatTile label="Most Active Category" value={data.kpis.top_category} />
        <StatTile label="Critical Open Issues" value={data.kpis.critical_open_issues} />
      </div>

      <PriorityPanel data={data.priority} />

      <div className="charts-grid">
        <CategoryBarChart data={data.categories} />
        <SentimentDivergingBar data={data.sentiment} />
        <SourceDonut data={data.sources} />
        <TrendLine data={data.trend} />
      </div>

      <AskFeedback />

      <WeeklySummary summary={data.summary.summary} />
    </div>
  );
}

export default App;
