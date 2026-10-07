"use client";
import { useRouter, usePathname } from "next/navigation";
import type { EventRow } from "@/lib/api";

const KINDS = [["R", "Race"], ["Q", "Qualifying"]];

export default function Selectors({ season, seasons, round, kind, events, extra = {} }: {
  season: number; seasons: number[]; round: number; kind: string; events: EventRow[]; extra?: Record<string, string>;
}) {
  const router = useRouter(); const path = usePathname();
  const go = (p: Record<string, string | number>) => {
    const q = new URLSearchParams({ season: String(season), round: String(round), kind, ...extra, ...Object.fromEntries(Object.entries(p).map(([k, v]) => [k, String(v)])) });
    router.push(`${path}?${q.toString()}`);
  };
  const sel = "rounded border border-line bg-panel2 px-2 py-1.5 text-sm text-ink";
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="text-xs text-mute">Season<br />
        <select className={sel} value={season} onChange={(e) => go({ season: e.target.value })}>{seasons.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label className="text-xs text-mute">Grand Prix<br />
        <select className={sel} value={round} onChange={(e) => go({ round: e.target.value })}>
          {events.map((e) => <option key={e.round} value={e.round}>R{e.round} {e.name}</option>)}</select></label>
      <label className="text-xs text-mute">Session<br />
        <select className={sel} value={kind} onChange={(e) => go({ kind: e.target.value })}>
          {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
    </div>
  );
}
