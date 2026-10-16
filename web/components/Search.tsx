"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, EventRow, Summary } from "@/lib/api";

type Item = { kind: "driver" | "team" | "circuit"; label: string; sub: string; href: string };

export default function Search({ season, round, kind }: { season: number; round: number; kind: string }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const [ev, sum] = await Promise.all([
          api<{ events: EventRow[] }>(`/events/${season}`),
          api<Summary>(`/summary/${season}/${round}/${kind}`),
        ]);
        if (!live) return;
        const drivers: Item[] = sum.rows.map((r) => ({
          kind: "driver", label: r.driver, sub: r.team,
          href: `/drivers/${r.driver}?season=${season}&round=${round}&kind=${kind}`,
        }));
        const teams = [...new Set(sum.rows.map((r) => r.team))].map((t) => ({
          kind: "team" as const, label: t,
          sub: sum.rows.filter((r) => r.team === t).map((r) => r.driver).join(" / "),
          href: `/teams?season=${season}&round=${round}&kind=${kind}`,
        }));
        const circuits: Item[] = ev.events.map((e) => ({
          kind: "circuit", label: e.circuit, sub: e.name,
          href: `/circuits?season=${season}`,
        }));
        setItems([...drivers, ...teams, ...circuits]);
      } catch { /* API offline */ }
    })();
    return () => { live = false; };
  }, [season, round, kind]);

  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (s.length < 2) return [];
    return items.filter((i) => `${i.label} ${i.sub}`.toLowerCase().includes(s)).slice(0, 8);
  }, [q, items]);

  return (
    <div className="relative w-full max-w-xs">
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Search drivers, teams, circuits…"
        className="w-full rounded border border-line bg-panel2 px-3 py-1.5 text-sm text-ink placeholder:text-mute/60"
      />
      {open && hits.length > 0 && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded border border-line bg-panel shadow-lg">
          {hits.map((h) => (
            <Link key={`${h.kind}-${h.label}`} href={h.href}
              className="flex items-center justify-between px-3 py-2 text-sm hover:bg-panel2">
              <span>{h.label} <span className="text-xs text-mute">{h.sub}</span></span>
              <span className="text-[10px] uppercase text-mute">{h.kind}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
