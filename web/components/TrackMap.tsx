"use client";
import { useMemo } from "react";
import type { TeleSample } from "@/lib/api";

// SVG track map coloured by speed delta (B - A). Blue = A faster, red = B faster.
export default function TrackMap({ a, b }: { a: TeleSample[]; b: TeleSample[] }) {
  const { path, segs, minX, minY, w, h } = useMemo(() => {
    const byDist = new Map<number, { x: number; y: number; d: number }>();
    for (const s of a) byDist.set(s.distance_m, { x: s.x, y: s.y, d: s.speed });
    const pts = a.map((s) => ({ x: s.x, y: s.y }));
    const bByDist = new Map(b.map((s) => [s.distance_m, s.speed] as const));
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const segs = a.map((s) => {
      const sb = bByDist.get(s.distance_m) ?? s.speed;
      return { x1: s.x, y1: s.y, delta: sb - s.speed };
    });
    const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") + " Z";
    return { path, segs, minX, minY, w: Math.max(maxX - minX, 1), h: Math.max(maxY - minY, 1) };
  }, [a, b]);

  const color = (d: number) => {
    const v = Math.max(-8, Math.min(8, d));
    if (Math.abs(v) < 1) return "#8a8a99";
    return v > 0 ? "#e06c75" : "#4aa3ff";
  };
  const W = 420, H = 300;
  const sx = (x: number) => ((x - minX) / w) * (W - 40) + 20;
  const sy = (y: number) => H - (((y - minY) / h) * (H - 40) + 20);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-72 w-full rounded border border-line bg-panel2">
        {segs.slice(0, -1).map((s, i) => {
          const n = segs[i + 1];
          return <line key={i} x1={sx(s.x1)} y1={sy(s.y1)} x2={sx(n.x1)} y2={sy(n.y1)}
            stroke={color(s.delta)} strokeWidth={3} strokeLinecap="round" opacity={0.9} />;
        })}
      </svg>
      <p className="mt-1 text-[11px] text-mute">
        Track coloured by speed delta: <span style={{ color: "#4aa3ff" }}>blue = first lap faster</span>,{" "}
        <span style={{ color: "#e06c75" }}>red = second lap faster</span>, grey = within 1 km/h.
        Shape is schematic on demo data; distances are to scale.
      </p>
    </div>
  );
}
