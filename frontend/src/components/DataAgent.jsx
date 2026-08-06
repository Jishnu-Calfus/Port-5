import { useState } from "react";
import { askAgent } from "../api";
import CategoryBarChart from "./CategoryBarChart";
import SentimentDivergingBar from "./SentimentDivergingBar";
import SourceDonut from "./SourceDonut";
import TrendLine from "./TrendLine";
import StatTile from "./StatTile";

// Maps the backend's chart_type string to the dashboard's existing chart
// components -- the same components the all-time/this-week views already
// use, just fed data the agent's SQL produced instead of a fixed endpoint.
const CHART_COMPONENTS = {
  bar: CategoryBarChart,
  diverging_bar: SentimentDivergingBar,
  donut: SourceDonut,
  line: TrendLine,
};

export default function DataAgent() {
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState(""); // the question the
  // current result actually answers -- kept separate from `question` so a
  // chart's title doesn't change if the user starts typing a new query
  // before this one's answer has rendered.
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAsk() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const answer = await askAgent(question);
      setResult(answer);
      setAskedQuestion(question);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const ChartComponent = result?.chart_type ? CHART_COMPONENTS[result.chart_type] : null;

  return (
    <>
      <div className="card">
        <div className="section-title">Ask The Data</div>
        <div className="ask-box">
          <input
            type="text"
            placeholder="e.g. compare fee complaints by source last quarter"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          />
          <button onClick={handleAsk} disabled={loading}>
            {loading ? "Querying..." : "Ask"}
          </button>
        </div>

        {error && <p className="error">{error}</p>}

        {result && (
          <>
            <p className="ask-answer">{result.answer}</p>
            <details className="agent-sql-detail">
              <summary>
                View SQL ({result.row_count} row{result.row_count === 1 ? "" : "s"})
              </summary>
              <pre>{result.sql}</pre>
            </details>
          </>
        )}
      </div>

      {/* Rendered as its own card, not nested inside the one above -- the
          chart components already wrap themselves in "card chart-card". */}
      {result?.chart_type === "stat" && (
        <StatTile label={askedQuestion} value={result.chart_data.value} />
      )}
      {ChartComponent && <ChartComponent data={result.chart_data} title={askedQuestion} />}

      {/* grouped_bar: a comparison question ("... for weeks of X and Y")
          returned more than one bar chart's worth of data -- one
          CategoryBarChart per group, side by side, each titled with which
          group it's showing. */}
      {result?.chart_type === "grouped_bar" && (
        <div className="charts-grid">
          {result.chart_data.map((group) => (
            <CategoryBarChart key={group.label} data={group.data} title={`${askedQuestion} — ${group.label}`} />
          ))}
        </div>
      )}
    </>
  );
}
