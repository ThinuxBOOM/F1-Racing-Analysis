import Link from "next/link";
import { api, EventRow, Summary, signed, f3 } from "@/lib/api";
import type { TeamRow } from "@/lib/api";
import Selectors from "@/components/Selectors";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string; kind?: string };
export const dynamic = "force-dynamic";

// Cars = the machine side of the team estimate. Shows car ranking plus how far
// each driver sits from their own team's mean (the "driver part").
export default async function CarsPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const kind = searchParams.kind === "Q" ? "Q" : "R";
  const q = `${season}/${round}/${kind}`;
  const [{ teams }, sum] = await Promise.all([
    api<{ teams: TeamRow[] }>(`/teams/${q}`),
    api<Summary>(`/summary/${q}`),
  ]);
  const paceByDriver = new Map(sum.rows.map((r) => [r.driver, r.gap_to_field_best_pace_s ?? 0]));
  const ev = events.find((e) => e.round === round);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Machine analysis</div>
        <h1 className="text-xl font-semibold">Cars <span className="text-mute">/ {ev?.name ?? ""}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          One car per team by construction (teammates are assumed to drive identical machinery).
          Car gap is the team-mean effect; driver spread is each driver&apos;s deviation from that mean.
          <strong className="text-warn"> Model estimate.</strong> <Link className="underline" href="/methodology#driver_vs_car">How?</Link>
        </p>
      </header>
      <Selectors season={season} seasons={seasons} round={round} kind={kind} events={events} />
      <div className="grid gap-3 md:grid-cols-2">
        {teams.map((t, i) => {
          const devs = t.drivers.map((d) => {
            const pace = paceByDriver.get(d) ?? 0;
            const teamMean = t.car_pace_s;
            return { d, pace, dev: pace - (teams.reduce((a, x) => a + x.car_pace_s, 0) / teams.length - (t.car_pace_s - teamMean)) };
          });
          return (
            <FadeIn key={t.team} delay={Math.min(i * 0.04, 0.3)}>
              <section className="card p-4">
                <div className="flex items-baseline justify-between">
                  <h2 className="text-sm font-medium">{t.team}</h2>
                  <span className="num text-sm text-mute">car {signed(t.gap_to_best_car_s)} s</span>
                </div>
                <div className="mt-3 space-y-2">
                  {t.drivers.map((d) => {
                    const row = sum.rows.find((r) => r.driver === d);
                    return (
                      <div key={d} className="flex items-center justify-between text-sm">
                        <Link className="underline decoration-line underline-offset-4"
                          href={`/drivers/${d}?season=${season}&round=${round}&kind=${kind}`}>{d}</Link>
                        <span className="num text-mute">
                          adj. pace {signed(row?.gap_to_field_best_pace_s)} s · n={row?.n_clean}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-3 text-[11px] text-mute">
                  Car {signed(t.gap_to_best_car_s)} s off best
                  {t.gap_ci95_s[0] != null && (
                    <> <span className="num">[{signed(t.gap_ci95_s[0])}, {signed(t.gap_ci95_s[1])}]</span></>)}.
                  Within-team differences reflect driver + circumstance, not car.
                </p>
              </section>
            </FadeIn>
          );
        })}
      </div>
    </div>
  );
}
