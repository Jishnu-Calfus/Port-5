import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function TrendLine({ data }) {
  return (
    <div className="card chart-card">
      <div className="section-title">Feedback Volume Over Time</div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ left: 0, right: 16 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <XAxis dataKey="date" stroke="var(--axis)" tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
          <YAxis stroke="var(--axis)" tick={{ fill: "var(--text-muted)", fontSize: 12 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)", borderRadius: 8 }}
            labelStyle={{ color: "var(--text-primary)" }}
          />
          <Line type="monotone" dataKey="count" stroke="var(--series-blue)" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
