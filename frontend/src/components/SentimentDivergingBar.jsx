import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// Diverging stacked bar centered on neutral: negative extends left (red pole),
// positive extends right (blue pole), neutral is split evenly across the
// zero line so its segment visually sits "at rest" between the two poles.
export default function SentimentDivergingBar({ data, title = "Sentiment by Category" }) {
  const chartData = data.map((row) => ({
    category: row.category,
    negative: -row.negative,
    neutralLeft: -(row.neutral / 2),
    neutralRight: row.neutral / 2,
    positive: row.positive,
  }));

  return (
    <div className="card chart-card">
      <div className="section-title">{title}</div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} layout="vertical" stackOffset="sign" margin={{ left: 100 }}>
          <CartesianGrid stroke="var(--gridline)" horizontal={false} />
          <XAxis type="number" stroke="var(--axis)" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="category"
            stroke="var(--axis)"
            tick={{ fill: "var(--text-secondary)", fontSize: 12 }}
            width={140}
          />
          <Tooltip
            contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8 }}
            labelStyle={{ color: "var(--text-primary)" }}
          />
          <ReferenceLine x={0} stroke="var(--axis)" />
          <Bar dataKey="negative" stackId="sentiment" fill="var(--diverging-negative)" name="negative" />
          <Bar dataKey="neutralLeft" stackId="sentiment" fill="var(--diverging-neutral)" legendType="none" name="neutral" />
          <Bar dataKey="neutralRight" stackId="sentiment" fill="var(--diverging-neutral)" legendType="none" name="neutral" />
          <Bar dataKey="positive" stackId="sentiment" fill="var(--series-blue)" radius={[0, 4, 4, 0]} name="positive" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
