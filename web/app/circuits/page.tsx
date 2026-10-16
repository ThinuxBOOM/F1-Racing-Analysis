import Link from "next/link";
import { api, EventRow, lapFmt, signed } from "@/lib/api";
import type { CircuitInfo } from "@/lib/api";
import FadeIn from "@/components/FadeIn";

export const dynamic = "force-dynamic";

export default async function CircuitsPage({ searchParams }: { searchParams: { season?: string } }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const { circuits } = await api<{ circuits: CircuitInfo[] }>(`/circuits/${season}`);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Circuit profiles</div>
        <h1 className="text-xl font-semibold">Circuits <span className="text-mute">/ {season}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Characteristics are computed from timing data only — never hand-labelled.
          Braking zones and full-throttle share need telemetry and are shown as pending.{" "}
          <Link className="underline" href="/methodology#circuit_profile">Methodology</Link>.
        </p>
      </header>
      <div className="grid gap-3 md:grid-cols-2">
        {circuits.map((c, i) => (
          <FadeIn key={c.round} delay={Math.min(i * 0.04, 0.3)}>
            <section className="card p-4">
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm font-medium">R{c.round} · {c.circuit}</h2>
                <span className="text-xs text-mute">{c.name}</span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div><dt className="label">Length</dt><dd className="num">{c.length_km ?? "-"} km · {c.total_laps ?? "-"} laps</dd></div>
                <div><dt className="label">Avg speed</dt><dd className="num">{c.avg_speed_kmh ?? "-"} km/h</dd></div>
                <div><dt className="label">Mean degradation</dt><dd className="num">{c.mean_deg_s_per_lap == null ? "-" : `${signed(c.mean_deg_s_per_lap)} s/lap`}</dd></div>
                <div><dt className="label">Overtaking index</dt><dd className="num">{c.overtake_index ?? "-"}</dd></div>
              </dl>
              <p className="mt-2 text-[11px] text-mute">{c.telemetry_note}</p>
              <Link className="mt-2 inline-block text-xs underline" href={`/?season=${season}&round=${c.round}&kind=R`}>
                Open dashboard →
              </Link>
            </section>
          </FadeIn>
        ))}
      </div>
    </div>
  );
}
