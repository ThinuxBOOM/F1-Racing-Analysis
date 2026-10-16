import Link from "next/link";
import { api, EventRow, Summary, Pace, lapFmt, signed } from "@/lib/api";
import type { TyreRow, Stint } from "@/lib/api";
import Selectors from "@/components/Selectors";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string; kind?: string };
export const dynamic = "force-dynamic";

export default async function TyresPage({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const kind = searchParams.kind === "Q" ? "Q" : "R";
  const q = `${season}/${round}/${kind}`;
  const [{ compounds }, st] = await Promise.all([
    api<{ compounds: TyreRow[] }>(`/tyres/${q}`),
    api<{ stints: Stint[] }>(`/stints/${q}`),
  ]);
  const ev = events.find((e) => e.round === round);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Tyre analysis</div>
        <h1 className="text-xl font-semibold">Tyres <span className="text-mute">/ {ev?.name ?? ""}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Raw medians mislead because faster cars favour certain compounds. Use the adjusted offset
          (driver/car/tyre-age mix removed). <strong className="text-warn">Model estimate.</strong>{" "}
          <Link className="underline" href="/methodology#tyre_compound">Methodology</Link>.
        </p>
      </header>
      <Selectors season={season} seasons={seasons} round={round} kind={kind} events={events} />
      <FadeIn>
        <section className="card overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="label text-left"><tr>
              {["Compound", "Adj. offset vs MEDIUM", "Median fuel-corr.", "Median age", "Degradation (s/lap)", "Laps / drivers", "Reliable?"].map((h) => (
                <th key={h} className="px-3 py-2 font-normal">{h}</th>))}
            </tr></thead>
            <tbody>
              {compounds.map((c) => (
                <tr key={c.compound} className="border-t border-line">
                  <td className="px-3 py-2 font-medium">{c.compound}{c.is_reference && <span className="ml-2 text-[10px] uppercase text-mute">ref</span>}</td>
                  <td className="num px-3 py-2">{c.adjusted_offset_vs_medium_s == null ? "-" : signed(c.adjusted_offset_vs_medium_s) + " s"}</td>
                  <td className="num px-3 py-2 text-mute">{c.median_fuel_corrected_s == null ? "-" : lapFmt(c.median_fuel_corrected_s)}</td>
                  <td className="num px-3 py-2 text-mute">{c.median_tyre_age ?? "-"}</td>
                  <td className="num px-3 py-2">{c.deg_s_per_lap == null ? "-" : `${signed(c.deg_s_per_lap)} ± ${c.deg_se?.toFixed(4) ?? "-"}`}</td>
                  <td className="num px-3 py-2 text-mute">{c.n_clean} / {c.n_drivers}</td>
                  <td className={`px-3 py-2 ${c.reliable ? "text-ok" : "text-warn"}`}>{c.reliable ? "yes" : "low sample"}</td>
                </tr>))}
            </tbody>
          </table>
          <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
            Adjusted offset = fixed-effects dummy (MEDIUM = 0). Degradation = OLS slope on tyre age, clean laps only.
            Compounds with fewer than 8 clean laps are flagged.
          </p>
        </section>
      </FadeIn>
      <section className="card overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-medium">Stint degradation (all drivers)</h2>
        <table className="w-full min-w-[680px] text-sm">
          <thead className="label text-left"><tr>
            {["Driver", "Stint", "Compound", "Laps", "Clean", "Degradation", "Reliable?"].map((h) => (
              <th key={h} className="px-3 py-2 font-normal">{h}</th>))}
          </tr></thead>
          <tbody>
            {st.stints.slice(0, 60).map((s, i) => (
              <tr key={i} className="border-t border-line">
                <td className="px-3 py-2">{s.driver}</td>
                <td className="num px-3 py-2">{s.stint} ({s.compound})</td>
                <td className="px-3 py-2 text-mute">{s.start_lap}-{s.end_lap}</td>
                <td className="num px-3 py-2">{s.n_laps}</td>
                <td className="num px-3 py-2">{s.n_clean}</td>
                <td className="num px-3 py-2">{s.deg_s_per_lap == null ? "-" : `${signed(s.deg_s_per_lap)} ± ${s.deg_se?.toFixed(4) ?? "-"}`}</td>
                <td className={`px-3 py-2 ${s.reliable ? "text-ok" : "text-warn"}`}>{s.reliable ? "yes" : "low sample"}</td>
              </tr>))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
