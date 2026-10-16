import Link from "next/link";
import { api, EventRow, signed, lapFmt } from "@/lib/api";
import type { StrategyRow, Undercut } from "@/lib/api";
import Selectors from "@/components/Selectors";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string };
export const dynamic = "force-dynamic";

export default async function StrategyPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const { strategies, undercuts } = await api<{ strategies: StrategyRow[]; undercuts: Undercut[] }>(
    `/strategy/${season}/${round}`);
  const ev = events.find((e) => e.round === round);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Pit strategy</div>
        <h1 className="text-xl font-semibold">Strategy <span className="text-mute">/ {ev?.name ?? ""}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Strategies and positions observed; effectiveness pace is a tyre-adjusted estimate.
          Undercuts need position data and are coarse — safety-car pits distort them.
        </p>
      </header>
      <Selectors season={season} seasons={seasons} round={round} kind="R" events={events} />
      <FadeIn>
        <section className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="label text-left"><tr>
              {["Driver", "Team", "Stops", "Strategy", "Pit laps", "Adj. pace", "Gap to best strategy"].map((h) => (
                <th key={h} className="px-3 py-2 font-normal">{h}</th>))}
            </tr></thead>
            <tbody>
              {strategies.map((s) => (
                <tr key={s.driver} className="border-t border-line">
                  <td className="px-3 py-2">
                    <Link className="underline decoration-line underline-offset-4"
                      href={`/drivers/${s.driver}?season=${season}&round=${round}&kind=R`}>{s.driver}</Link>
                  </td>
                  <td className="px-3 py-2 text-mute">{s.team}</td>
                  <td className="num px-3 py-2">{s.n_stops}</td>
                  <td className="px-3 py-2">{s.strategy}</td>
                  <td className="num px-3 py-2 text-mute">
                    {s.pit_stops.map((p) => `L${p.lap} ${p.duration_s?.toFixed(1) ?? "-"}s P${p.position_before ?? "-"}→P${p.position_after ?? "-"}`).join(" · ") || "-"}
                  </td>
                  <td className="num px-3 py-2">{s.median_adj_pace_s == null ? "-" : lapFmt(s.median_adj_pace_s)}</td>
                  <td className="num px-3 py-2 text-mute">{signed(s.strategy_gap_to_best_s)} s</td>
                </tr>))}
            </tbody>
          </table>
        </section>
      </FadeIn>
      <section className="card p-4">
        <h2 className="mb-2 text-sm font-medium">Undercuts ({undercuts.length})</h2>
        {undercuts.length === 0 ? <p className="text-sm text-mute">None detected this race.</p> : (
          <ul className="space-y-1 text-sm">
            {undercuts.map((u, i) => (
              <li key={i} className="text-mute">
                <strong className="text-ink">{u.passer}</strong> undercut {u.rival}: pitted lap {u.pass_lap}
                (rival lap {u.rival_pit_lap}), {u.before} → {u.after}.
              </li>))}
          </ul>)}
      </section>
    </div>
  );
}
