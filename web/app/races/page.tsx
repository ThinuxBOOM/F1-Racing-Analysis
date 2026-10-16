import Link from "next/link";
import { api, EventRow, lapFmt, signed } from "@/lib/api";
import type { StandingDriver, StandingTeam } from "@/lib/api";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string };
export const dynamic = "force-dynamic";

export default async function RacesPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const [{ event, results, pit_stops, quality }, st] = await Promise.all([
    api<{ event: EventRow; kind: string; results: any[]; pit_stops: any[]; quality: any }>(`/races/${season}/${round}`),
    api<{ standings: { drivers: StandingDriver[]; teams: StandingTeam[] } }>(`/standings/${season}`),
  ]);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Race weekends</div>
        <h1 className="text-xl font-semibold">{event.name} <span className="text-mute">/ {event.circuit}</span></h1>
        <p className="mt-1 text-sm text-mute">
          Results are observed facts. For why the gaps look that way, open the{" "}
          <Link className="underline" href={`/?season=${season}&round=${round}&kind=R`}>Dashboard</Link>.
        </p>
      </header>

      <div className="flex flex-wrap gap-1.5">
        {events.map((e) => (
          <Link key={e.round} href={`/races?season=${season}&round=${e.round}`}
            className={`rounded border px-2 py-1 text-xs ${e.round === round ? "border-info bg-panel2 text-ink" : "border-line text-mute"}`}>
            R{e.round} {e.name}
          </Link>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <FadeIn>
          <section className="card overflow-hidden lg:col-span-2">
            <h2 className="px-3 pt-3 text-sm font-medium">Classification</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead className="label text-left"><tr>
                  {["Pos", "Driver", "Team", "Status", "Pts"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
                </tr></thead>
                <tbody>
                  {results.map((r: any) => (
                    <tr key={r.driver} className="border-t border-line">
                      <td className="num px-3 py-2">{r.finish_pos ?? "-"}</td>
                      <td className="px-3 py-2">
                        <Link className="underline decoration-line underline-offset-4"
                          href={`/drivers/${r.driver}?season=${season}&round=${round}&kind=R`}>{r.driver}</Link>
                      </td>
                      <td className="px-3 py-2 text-mute">{r.team}</td>
                      <td className="px-3 py-2 text-mute">{r.status}</td>
                      <td className="num px-3 py-2">{r.points}</td>
                    </tr>))}
                </tbody>
              </table>
            </div>
          </section>
        </FadeIn>
        <FadeIn delay={0.08}>
          <section className="card p-4">
            <h2 className="text-sm font-medium">Pit stops ({pit_stops.length})</h2>
            {pit_stops.length === 0 ? <p className="mt-2 text-sm text-mute">None recorded.</p> : (
              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
                {pit_stops.slice(0, 40).map((p: any, i: number) => (
                  <li key={i} className="num text-mute">
                    {p.driver} · lap {p.lap} · {p.duration_s?.toFixed(1) ?? "-"}s
                    {p.position_before != null && <> · P{p.position_before}→P{p.position_after ?? "-"}</>}
                  </li>))}
              </ul>)}
            {quality?.flags?.length > 0 && (
              <div className="mt-3 border-t border-line pt-2 text-xs text-warn">
                <div className="label mb-1 text-warn">Data quality</div>
                <ul className="list-disc pl-4">{quality.flags.map((f: string) => <li key={f}>{f}</li>)}</ul>
              </div>)}
          </section>
        </FadeIn>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="card overflow-x-auto">
          <h2 className="px-3 pt-3 text-sm font-medium">Driver standings ({season})</h2>
          <table className="w-full text-sm">
            <thead className="label text-left"><tr>
              {["#", "Driver", "Team", "Pts", "W", "Pod"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
            </tr></thead>
            <tbody>
              {st.standings.drivers.map((d, i) => (
                <tr key={d.driver} className="border-t border-line">
                  <td className="num px-3 py-2">{i + 1}</td>
                  <td className="px-3 py-2">{d.driver}</td>
                  <td className="px-3 py-2 text-mute">{d.team}</td>
                  <td className="num px-3 py-2">{d.points}</td>
                  <td className="num px-3 py-2">{d.wins}</td>
                  <td className="num px-3 py-2">{d.podiums}</td>
                </tr>))}
            </tbody>
          </table>
        </section>
        <section className="card overflow-x-auto">
          <h2 className="px-3 pt-3 text-sm font-medium">Team standings ({season})</h2>
          <table className="w-full text-sm">
            <thead className="label text-left"><tr>
              {["#", "Team", "Pts", "Wins", "Drivers"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
            </tr></thead>
            <tbody>
              {st.standings.teams.map((t, i) => (
                <tr key={t.team} className="border-t border-line">
                  <td className="num px-3 py-2">{i + 1}</td>
                  <td className="px-3 py-2">{t.team}</td>
                  <td className="num px-3 py-2">{t.points}</td>
                  <td className="num px-3 py-2">{t.wins}</td>
                  <td className="px-3 py-2 text-mute">{t.drivers.join(" / ")}</td>
                </tr>))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
