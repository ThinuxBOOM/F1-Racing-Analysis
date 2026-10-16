import Link from "next/link";
import { api, EventRow, signed, f3 } from "@/lib/api";
import type { TeamRow } from "@/lib/api";
import Selectors from "@/components/Selectors";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string; kind?: string };
export const dynamic = "force-dynamic";

export default async function TeamsPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const kind = searchParams.kind === "Q" ? "Q" : "R";
  const q = `${season}/${round}/${kind}`;
  const { teams } = await api<{ teams: TeamRow[] }>(`/teams/${q}`);
  const ev = events.find((e) => e.round === round);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Team performance</div>
        <h1 className="text-xl font-semibold">Teams <span className="text-mute">/ {ev?.name ?? ""}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Car pace is a <strong className="text-warn">model estimate</strong> (mean of tyre-adjusted driver effects).
          Points and positions are observed. See <Link className="underline" href="/methodology#team_car_pace">Methodology</Link>.
        </p>
      </header>
      <Selectors season={season} seasons={seasons} round={round} kind={kind} events={events} />
      <FadeIn>
        <section className="card overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="label text-left"><tr>
              {["Team", "Drivers", "Car gap to best", "95% CI", "Points", "Finishes", "Clean laps"].map((h) => (
                <th key={h} className="px-3 py-2 font-normal">{h}</th>))}
            </tr></thead>
            <tbody>
              {teams.map((t) => (
                <tr key={t.team} className="border-t border-line hover:bg-panel2">
                  <td className="px-3 py-2 font-medium">{t.team}</td>
                  <td className="px-3 py-2 text-mute">{t.drivers.map((d) => (
                    <Link key={d} className="mr-2 underline decoration-line underline-offset-4"
                      href={`/drivers/${d}?season=${season}&round=${round}&kind=${kind}`}>{d}</Link>))}</td>
                  <td className="num px-3 py-2">{signed(t.gap_to_best_car_s)} s</td>
                  <td className="num px-3 py-2 text-mute">
                    {t.gap_ci95_s[0] == null ? "-" : `[${signed(t.gap_ci95_s[0])}, ${signed(t.gap_ci95_s[1])}]`}
                  </td>
                  <td className="num px-3 py-2">{t.points}</td>
                  <td className="num px-3 py-2 text-mute">{t.finish_positions.join(", ") || "-"}</td>
                  <td className="num px-3 py-2">{t.n_clean}</td>
                </tr>))}
            </tbody>
          </table>
          <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
            Gap to best car removes fuel, compound and tyre-age mix. An interval crossing zero vs the leader means
            the data cannot rule out parity. Shared driver strength is credited to the car by construction.
          </p>
        </section>
      </FadeIn>
    </div>
  );
}
