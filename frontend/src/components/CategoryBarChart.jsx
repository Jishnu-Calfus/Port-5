import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function CategoryBarChart({ data }) {
  return (
    <div className="card chart-card">
      <div className="section-title">Feedback Volume by Category</div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} layout="vertical" margin={{ left: 100 }}>
          <CartesianGrid stroke="var(--gridline)" horizontal={false} />
          <XAxis type="number" stroke="var(--axis)" tick={{ fill: "var(--text-muted)", fontSize: 12 }} allowDecimals={false} />
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
          <Bar dataKey="volume" fill="var(--series-blue)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
