"use client";
import { Line, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceDot } from "recharts";
import type { TeleSample, Corner } from "@/lib/api";

export default function TelemetryChart({ a, b, labelA, labelB, corners }: {
  a: TeleSample[]; b: TeleSample[]; labelA: string; labelB: string; corners: Corner[];
}) {
  const byDist = new Map<number, any>();
  for (const s of a) byDist.set(s.distance_m, { d: s.distance_m, A: s.speed, A_thr: s.throttle });
  for (const s of b) {
    const r = byDist.get(s.distance_m) ?? { d: s.distance_m };
    r.B = s.speed; r.B_thr = s.throttle; byDist.set(s.distance_m, r);
  }
  const data = [...byDist.values()].sort((x, y) => x.d - y.d);
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid stroke="#262633" strokeDasharray="2 4" />
          <XAxis dataKey="d" stroke="#8a8a99" tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} />
          <YAxis stroke="#8a8a99" tick={{ fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v}`} width={48} />
          <Tooltip contentStyle={{ background: "#13131a", border: "1px solid #262633", fontSize: 12 }}
            formatter={(v: number, name: string) => [`${v.toFixed(1)} km/h`, name]} labelFormatter={(v) => `${v} m`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="A" name={labelA} stroke="#4aa3ff" dot={false} strokeWidth={1.6} connectNulls={false} />
          <Line dataKey="B" name={labelB} stroke="#e06c75" dot={false} strokeWidth={1.6} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-[11px] text-mute">
        Speed vs distance ({corners.length} corners detected: apexes at {corners.map((c) => `${c.apex_m.toFixed(0)}m`).join(", ")}).
        Throttle/brake traces are in the table below.
      </p>
    </div>
  );
}
