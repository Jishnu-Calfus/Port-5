import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

// 3 unordered categories (Reviews/Tickets/Survey), no polarity or magnitude
// ordering between them -- a donut is a legitimate part-to-whole form here,
// unlike sentiment, which is ordered and gets the diverging bar instead.
const COLORS = ["var(--series-blue)", "var(--series-orange)", "var(--series-aqua)"];

export default function SourceDonut({ data }) {
  return (
    <div className="card chart-card">
      <div className="section-title">Feedback by Source</div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="source"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            label={({ source, percent }) => `${source} ${(percent * 100).toFixed(0)}%`}
            labelLine={{ stroke: "var(--text-muted)" }}
          >
            {data.map((entry, i) => (
              <Cell key={entry.source} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8 }} />
          <Legend wrapperStyle={{ color: "var(--text-secondary)", fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
