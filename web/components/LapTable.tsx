"use client";
import { useMemo, useState } from "react";
import type { PaceLap } from "@/lib/api";
import { lapFmt } from "@/lib/api";

// Virtualised lap explorer: handles 500+ rows without rendering them all.
export default function LapTable({ laps }: { laps: PaceLap[] }) {
  const [q, setQ] = useState("");
  const [onlyClean, setOnlyClean] = useState(true);
  const rows = useMemo(() => {
    const s = q.trim().toLowerCase();
    return laps.filter((l) => {
      if (onlyClean && !l.is_clean) return false;
      if (s && !`${l.driver} ${l.compound ?? ""} ${l.lap_number}`.toLowerCase().includes(s)) return false;
      return true;
    }).sort((a, b) => a.lap_number - b.lap_number || a.driver.localeCompare(b.driver));
  }, [laps, q, onlyClean]);

  const ROW = 30;
  const HEIGHT = 320;
  const [scroll, setScroll] = useState(0);
  const start = Math.max(0, Math.floor(scroll / ROW) - 3);
  const count = Math.ceil(HEIGHT / ROW) + 6;
  const slice = rows.slice(start, start + count);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter driver / compound / lap…"
          className="w-64 max-w-full rounded border border-line bg-panel2 px-2 py-1 text-xs text-ink" />
        <label className="flex items-center gap-1 text-xs text-mute">
          <input type="checkbox" checked={onlyClean} onChange={(e) => setOnlyClean(e.target.checked)} />
          clean only
        </label>
        <span className="text-[11px] text-mute">{rows.length} laps</span>
      </div>
      <div className="grid grid-cols-6 gap-2 px-2 py-1 text-[11px] uppercase tracking-wide text-mute">
        <span>Lap</span><span>Driver</span><span>Time</span><span>Fuel-corr.</span><span>Compound</span><span>Flag</span>
      </div>
      <div style={{ height: HEIGHT, overflowY: "auto" }} onScroll={(e) => setScroll(e.currentTarget.scrollTop)}
        className="overflow-x-auto rounded border border-line">
        <div style={{ height: rows.length * ROW, position: "relative" }}>
          <div style={{ transform: `translateY(${start * ROW}px)` }}>
            {slice.map((l, k) => (
              <div key={`${l.driver}-${l.lap_number}-${start + k}`} style={{ height: ROW }}
                className="num grid grid-cols-6 items-center gap-2 border-t border-line px-2 text-xs">
                <span>{l.lap_number}</span>
                <span>{l.driver}</span>
                <span>{l.lap_time_s == null ? "-" : lapFmt(l.lap_time_s)}</span>
                <span>{l.fuel_corr_time_s == null ? "-" : lapFmt(l.fuel_corr_time_s)}</span>
                <span>{l.compound ?? "-"} a{l.tyre_age ?? "-"}</span>
                <span className={l.is_clean ? "text-ok" : "text-warn"}>{l.is_clean ? "clean" : l.exclude_reason}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-1 text-[11px] text-mute">Virtualised: renders ~{count} of {rows.length} rows.</p>
    </div>
  );
}
