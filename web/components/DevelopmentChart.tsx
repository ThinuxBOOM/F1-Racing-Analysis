"use client";
import { Line, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const COLORS = ["#4aa3ff", "#e0a43a", "#3fb27f", "#c678dd", "#e06c75"];

export default function DevelopmentChart({ development }: { development: any }) {
  const rounds: number[] = development.rounds;
  const teams: string[] = Object.keys(development.teams);
  const data = rounds.map((r) => {
    const row: any = { round: `R${r}` };
    for (const t of teams) {
      const pt = development.teams[t].points.find((p: any) => p.round === r);
      row[t] = pt ? pt.gap_s : null;
    }
    return row;
  });
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid stroke="#262633" strokeDasharray="2 4" />
          <XAxis dataKey="round" stroke="#8a8a99" tick={{ fontSize: 11 }} />
          <YAxis stroke="#8a8a99" tick={{ fontSize: 11 }} tickFormatter={(v) => Number(v).toFixed(2)} width={48} />
          <Tooltip contentStyle={{ background: "#13131a", border: "1px solid #262633", fontSize: 12 }}
            formatter={(v: number) => [`${Number(v).toFixed(3)} s`, "gap"]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {teams.map((t, i) => (
            <Line key={t} dataKey={t} stroke={COLORS[i % COLORS.length]} dot={false} strokeWidth={1.6} connectNulls={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
