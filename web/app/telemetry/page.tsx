import Link from "next/link";
import { api, EventRow, Summary, signed } from "@/lib/api";
import type { TeleSample, Corner, CornerDelta } from "@/lib/api";
import Selectors from "@/components/Selectors";
import TelemetryChart from "@/components/TelemetryChart";
import TrackMap from "@/components/TrackMap";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string; kind?: string; a?: string; lapA?: string; b?: string; lapB?: string };
export const dynamic = "force-dynamic";

export default async function TelemetryPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const kind = "R";
  const sum = await api<Summary>(`/summary/${season}/${round}/${kind}`);
  const codes = sum.rows.map((r) => r.driver);
  const a = searchParams.a && codes.includes(searchParams.a) ? searchParams.a : codes[0];
  const b = searchParams.b && codes.includes(searchParams.b) ? searchParams.b : codes[codes.length - 1];

  // default laps: middle clean lap for each driver
  const [paceA, paceB] = await Promise.all([
    api<{ laps: any[] }>(`/pace/${season}/${round}/${kind}`),
  ]).then(([p]) => [p, p]);
  const cleanLap = (drv: string, fallback: number) => {
    const laps = paceA.laps.filter((l: any) => l.driver === drv && l.is_clean);
    if (!laps.length) return fallback;
    return laps[Math.floor(laps.length / 2)].lap_number;
  };
  const lapA = Number(searchParams.lapA ?? cleanLap(a, 10));
  const lapB = Number(searchParams.lapB ?? cleanLap(b, 10));

  let teleA: TeleSample[] = [], teleB: TeleSample[] = [], corners: Corner[] = [];
  let deltas: { corners: CornerDelta[]; n_corners: number; mean_speed_delta_kmh: number; predicted_lap_delta_s: number } | null = null;
  let err: string | null = null;
  try {
    const [ta, dd] = await Promise.all([
      api<{ samples: TeleSample[]; corners: Corner[] }>(`/telemetry/${season}/${round}/${kind}/${a}/${lapA}`),
      api<{ result: any }>(`/corner-deltas/${season}/${round}/${kind}/${a}/${lapA}/${b}/${lapB}`),
    ]);
    teleA = ta.samples; corners = ta.corners;
    const tb = await api<{ samples: TeleSample[] }>(`/telemetry/${season}/${round}/${kind}/${b}/${lapB}`);
    teleB = tb.samples;
    deltas = dd.result;
  } catch (e: any) {
    err = e?.message ?? "telemetry unavailable";
  }

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Lap overlays and corner decomposition</div>
        <h1 className="text-xl font-semibold">Telemetry</h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Distance-aligned speed overlay plus per-corner entry/apex/exit deltas.
          On demo data traces are synthetic; on FastF1 data they are measured (2018+).
          Alignment error ~±12 m. <Link className="underline" href="/methodology#corner_analysis">Methodology</Link>.
        </p>
      </header>

      <form className="flex flex-wrap items-end gap-3" action="/telemetry">
        <input type="hidden" name="season" value={season} />
        <input type="hidden" name="round" value={round} />
        <Pick name="a" label="Lap A driver" value={a} opts={codes.map((c) => [c, c])} />
        <label className="text-xs text-mute">Lap A<br />
          <input name="lapA" defaultValue={lapA} type="number" min={1} max={80}
            className="w-20 rounded border border-line bg-panel2 px-2 py-1.5 text-sm text-ink" /></label>
        <Pick name="b" label="Lap B driver" value={b} opts={codes.map((c) => [c, c])} />
        <label className="text-xs text-mute">Lap B<br />
          <input name="lapB" defaultValue={lapB} type="number" min={1} max={80}
            className="w-20 rounded border border-line bg-panel2 px-2 py-1.5 text-sm text-ink" /></label>
        <button className="rounded border border-line bg-panel2 px-3 py-1.5 text-sm hover:border-info">Compare</button>
      </form>

      {err ? <div className="card p-4 text-sm text-warn">{err}</div> : deltas && (
        <>
          <FadeIn>
            <section className="card p-4">
              <div className="mb-2 flex flex-wrap justify-between gap-2 text-sm">
                <h2 className="font-medium">{a} lap {lapA} vs {b} lap {lapB}</h2>
                <span className="num text-mute">
                  mean {signed(deltas.mean_speed_delta_kmh)} km/h (B−A) · predicted lap {signed(deltas.predicted_lap_delta_s)} s
                </span>
              </div>
              <TelemetryChart a={teleA} b={teleB} labelA={`${a} ${lapA}`} labelB={`${b} ${lapB}`} corners={corners} />
            </section>
          </FadeIn>
          <div className="grid gap-3 lg:grid-cols-2">
            <FadeIn delay={0.05}>
              <section className="card p-4">
                <h2 className="mb-2 text-sm font-medium">Track map (speed delta)</h2>
                <TrackMap a={teleA} b={teleB} />
              </section>
            </FadeIn>
            <FadeIn delay={0.08}>
              <section className="card overflow-x-auto">
                <h2 className="px-3 pt-3 text-sm font-medium">Corner deltas (B − A)</h2>
                <table className="w-full min-w-[480px] text-sm">
                  <thead className="label text-left"><tr>
                    {["C", "Entry Δ", "Apex Δ", "Exit Δ", "Time Δ"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {deltas.corners.map((c) => (
                      <tr key={c.corner} className="border-t border-line">
                        <td className="num px-3 py-2">T{c.corner} <span className="text-mute">@{c.apex_m.toFixed(0)}m</span></td>
                        <td className="num px-3 py-2">{signed(c.entry_delta_kmh)}</td>
                        <td className="num px-3 py-2">{signed(c.apex_delta_kmh)}</td>
                        <td className="num px-3 py-2">{signed(c.exit_delta_kmh)}</td>
                        <td className="num px-3 py-2">{signed(c.time_delta_s)} s</td>
                      </tr>))}
                  </tbody>
                </table>
                <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
                  Positive speed Δ = {b} faster; positive time Δ = {b} slower through that corner.
                  Compare multiple lap pairs before concluding — single-lap deltas include traffic and mistakes.
                </p>
              </section>
            </FadeIn>
          </div>
        </>
      )}
    </div>
  );
}

function Pick({ name, label, value, opts }: { name: string; label: string; value: string; opts: string[][] }) {
  return (
    <label className="text-xs text-mute">{label}<br />
      <select name={name} defaultValue={value} className="rounded border border-line bg-panel2 px-2 py-1.5 text-sm text-ink">
        {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select></label>
  );
}
