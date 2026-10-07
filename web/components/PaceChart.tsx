"use client";
import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PaceLap } from "@/lib/api";

const COLORS = ["#4aa3ff", "#e0a43a", "#3fb27f", "#c678dd", "#e06c75", "#56b6c2", "#d19a66", "#98c379", "#abb2bf", "#be5046"];

export default function PaceChart({ laps, field, drivers, initial }: {
  laps: PaceLap[]; field: { lap_number: number; field_median_s: number }[]; drivers: string[]; initial: string[];
}) {
  const [sel, setSel] = useState<string[]>(initial);
  const [compound, setCompound] = useState<string>("ALL");
  const data = useMemo(() => {
    const byLap = new Map<number, Record<string, number>>();
    for (const f of field) byLap.set(f.lap_number, { lap: f.lap_number, FIELD: f.field_median_s });
    for (const l of laps) {
      if (!l.is_clean || l.fuel_corr_time_s == null || !sel.includes(l.driver)) continue;
      if (compound !== "ALL" && l.compound !== compound) continue;
      const row = byLap.get(l.lap_number) ?? { lap: l.lap_number };
      row[l.driver] = l.fuel_corr_time_s; byLap.set(l.lap_number, row);
    }
    return [...byLap.values()].sort((a, b) => a.lap - b.lap);
  }, [laps, field, sel, compound]);
  const toggle = (d: string) => setSel((s) => (s.includes(d) ? s.filter((x) => x !== d) : [...s, d]));
  const btn = (on: boolean) => `rounded border px-2 py-1 text-xs ${on ? "border-info text-ink bg-panel2" : "border-line text-mute"}`;
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {drivers.map((d) => <button key={d} className={btn(sel.includes(d))} onClick={() => toggle(d)}>{d}</button>)}
        <span className="mx-2 border-l border-line" />
        {["ALL", "SOFT", "MEDIUM", "HARD"].map((c) => <button key={c} className={btn(compound === c)} onClick={() => setCompound(c)}>{c}</button>)}
      </div>
      <div className="h-80 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
            <CartesianGrid stroke="#262633" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#8a8a99" tick={{ fontSize: 11 }} label={{ value: "Lap", position: "insideBottom", offset: -2, fill: "#8a8a99", fontSize: 11 }} />
            <YAxis stroke="#8a8a99" tick={{ fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => Number(v).toFixed(1)} width={48} />
            <Tooltip contentStyle={{ background: "#13131a", border: "1px solid #262633", fontSize: 12 }} formatter={(v: number) => v.toFixed(3) + " s"} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line dataKey="FIELD" name="Field median" stroke="#8a8a99" strokeDasharray="4 3" dot={false} connectNulls />
            {sel.map((d) => <Line key={d} dataKey={d} stroke={COLORS[drivers.indexOf(d) % COLORS.length]} dot={false} strokeWidth={1.6} connectNulls={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[11px] text-mute">Clean laps only, fuel-corrected (assumed 0.035 s/lap). Pit, safety-car, deleted and outlier laps are excluded, so gaps in a line are intentional.</p>
    </div>
  );
}
