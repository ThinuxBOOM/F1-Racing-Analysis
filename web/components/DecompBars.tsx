import type { Decomp, Interval } from "@/lib/api";
import { signed } from "@/lib/api";

// Horizontal bars with 95% interval whiskers on a shared symmetric scale.
export default function DecompBars({ d }: { d: Decomp }) {
  const rows: [string, Interval, string][] = [
    ["Car", d.components.car, "bg-info"],
    ["Driver", d.components.driver, "bg-ok"],
    ["Strategy / tyres / traffic", d.components.strategy_tyres_traffic, "bg-warn"],
  ];
  const max = Math.max(0.1, ...rows.flatMap(([, i]) => [Math.abs(i.ci95_s[0]), Math.abs(i.ci95_s[1])])) * 1.1;
  const pct = (v: number) => 50 + (v / max) * 50;
  return (
    <div className="space-y-4">
      {rows.map(([label, i, color]) => (
        <div key={label}>
          <div className="mb-1 flex justify-between text-xs">
            <span>{label}</span>
            <span className="num text-mute">{signed(i.estimate_s)} s <span className="text-mute/70">[{signed(i.ci95_s[0])}, {signed(i.ci95_s[1])}]</span></span>
          </div>
          <div className="relative h-5 rounded bg-panel2">
            <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
            <div className={`absolute inset-y-1 ${color} opacity-80`} style={{ left: `${Math.min(pct(0), pct(i.estimate_s))}%`, width: `${Math.abs(pct(i.estimate_s) - pct(0))}%` }} />
            <div className="absolute top-1/2 h-px bg-ink" style={{ left: `${pct(i.ci95_s[0])}%`, width: `${pct(i.ci95_s[1]) - pct(i.ci95_s[0])}%` }} />
          </div>
        </div>
      ))}
      <p className="text-[11px] text-mute">Bar = estimate. Line = 95% interval. If the line crosses the centre, the data cannot rule out zero. Negative = {d.driver_a} faster.</p>
    </div>
  );
}
