"use client";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, Legend } from "recharts";

const COL: Record<string, string> = { SOFT: "#e06c75", MEDIUM: "#e0a43a", HARD: "#abb2bf" };

export default function ScatterByCompound({ laps }: { laps: { lap: number; t: number; compound: string }[] }) {
  const groups = ["SOFT", "MEDIUM", "HARD"].map((c) => ({ c, d: laps.filter((l) => l.compound === c) })).filter((g) => g.d.length);
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <ScatterChart margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid stroke="#262633" strokeDasharray="2 4" />
          <XAxis type="number" dataKey="lap" name="Lap" stroke="#8a8a99" tick={{ fontSize: 11 }} />
          <YAxis type="number" dataKey="t" name="Time" stroke="#8a8a99" tick={{ fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => Number(v).toFixed(1)} width={48} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "#13131a", border: "1px solid #262633", fontSize: 12 }} formatter={(v: number) => v.toFixed(3)} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {groups.map((g) => <Scatter key={g.c} name={g.c} data={g.d} fill={COL[g.c]} />)}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
