import Link from "next/link";
import { api, EventRow, Pace, Quality, Summary, f3, lapFmt, signed } from "@/lib/api";
import Selectors from "@/components/Selectors";
import PaceChart from "@/components/PaceChart";

type SP = { season?: string; round?: string; kind?: string };

export const dynamic = "force-dynamic";

export default async function Dashboard({ searchParams }: { searchParams: SP }) {
  let seasons: number[], events: EventRow[];
  try {
    seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  } catch {
    return <ApiDown />;
  }
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const kind = searchParams.kind === "Q" ? "Q" : "R";
  const q = `${season}/${round}/${kind}`;
  const [sum, pace, qual] = await Promise.all([
    api<Summary>(`/summary/${q}`), api<Pace>(`/pace/${q}`), api<{ report: Quality }>(`/quality/${q}`),
  ]);
  const ev = events.find((e) => e.round === round);
  const rows = sum.rows;
  const winner = rows[0];
  const bestPace = [...rows].sort((a, b) => (a.median_clean_pace_s ?? 1e9) - (b.median_clean_pace_s ?? 1e9))[0];
  const drivers = rows.map((r) => r.driver);
  const link = (d: string) => `/drivers/${d}?season=${season}&round=${round}&kind=${kind}`;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">{ev?.name} <span className="text-mute">/ {ev?.circuit}</span></h1>
        <p className="mt-1 text-sm text-mute">{kind === "R" ? "Race" : "Qualifying"} analysis. Every figure is cleaned and fuel-corrected; see <Link className="underline" href="/methodology">Methodology</Link>.</p>
      </header>
      <Selectors season={season} seasons={seasons} round={round} kind={kind} events={events} />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label={kind === "R" ? "Winner" : "Pole"} value={winner?.driver} sub={winner?.team} />
        <Kpi label="Best clean pace" value={bestPace?.driver} sub={lapFmt(bestPace?.median_clean_pace_s)} />
        <Kpi label="Sector leaders" value={Object.entries(sum.sector_leaders).map(([k, v]) => `${k.toUpperCase()} ${v}`).join("  ")} sub="best clean sector time" small />
        <Kpi label="Data completeness" value={`${(qual.report.mean_completeness * 100).toFixed(0)}%`} sub="laps surviving the clean filter" />
      </section>

      <section className="card p-4">
        <h2 className="mb-3 text-sm font-medium">Pace by lap</h2>
        <PaceChart laps={pace.laps} field={pace.field_median} drivers={drivers} initial={drivers.slice(0, 3)} />
      </section>

      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="label text-left"><tr>
            {["Pos", "Driver", "Team", "Grid", "Best lap", "Gap", "Adj. pace gap", "Consistency", "vs teammate (95% CI)"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.driver} className="border-t border-line hover:bg-panel2">
                <td className="num px-3 py-2">{r.finish_pos ?? "-"}</td>
                <td className="px-3 py-2"><Link className="underline decoration-line underline-offset-4" href={link(r.driver)}>{r.driver}</Link></td>
                <td className="px-3 py-2 text-mute">{r.team}</td>
                <td className="num px-3 py-2">{r.grid_pos ?? "-"}</td>
                <td className="num px-3 py-2">{lapFmt(r.best_lap_s)}</td>
                <td className="num px-3 py-2 text-mute">{signed(r.gap_to_best_s)}</td>
                <td className="num px-3 py-2 text-mute">{signed(r.gap_to_field_best_pace_s)}</td>
                <td className="num px-3 py-2">{r.consistency ? r.consistency.score.toFixed(0) : "-"}</td>
                <td className="px-3 py-2" title={r.teammate?.verdict}>
                  {r.teammate ? <span className="num">{signed(r.teammate.delta_s)} <span className="text-mute">[{signed(r.teammate.ci_low)}, {signed(r.teammate.ci_high)}]</span></span> : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
          Adj. pace gap and teammate gap come from a model that removes fuel, compound and tyre-age effects from clean laps (raw medians are not comparable across tyre strategies). Negative teammate gap = this driver faster; an interval spanning zero means no clear difference (hover for the reading). Consistency is a single-session, field-relative score and is noisy: differences under about 25 points are not meaningful. Best lap is raw.
        </p>
      </section>

      {qual.report.flags.length > 0 && (
        <section className="card border-warn/40 p-4 text-sm text-warn">
          <div className="label mb-1 text-warn">Data quality flags</div>
          <ul className="list-disc pl-5">{qual.report.flags.map((f) => <li key={f}>{f}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

function Kpi({ label, value, sub, small }: { label: string; value?: string; sub?: string; small?: boolean }) {
  return (
    <div className="card p-3">
      <div className="label">{label}</div>
      <div className={`mt-1 font-semibold ${small ? "text-sm" : "text-lg"}`}>{value ?? "-"}</div>
      <div className="num mt-0.5 text-xs text-mute">{sub}</div>
    </div>
  );
}

function ApiDown() {
  return (
    <div className="card p-6 text-sm">
      <h1 className="mb-2 text-lg font-semibold">Analytics API not reachable</h1>
      <p className="text-mute">Start it with <code className="num">cd services/analytics &amp;&amp; DATA_SOURCE=mock uvicorn api:app --port 8000</code>, then reload.</p>
    </div>
  );
}
