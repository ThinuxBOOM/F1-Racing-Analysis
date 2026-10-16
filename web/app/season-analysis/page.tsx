import Link from "next/link";
import { api, signed } from "@/lib/api";
import type { MixedResult, FuelEst } from "@/lib/api";
import FadeIn from "@/components/FadeIn";
import DevelopmentChart from "@/components/DevelopmentChart";

export const dynamic = "force-dynamic";

export default async function SeasonAnalysis({ searchParams }: { searchParams: { season?: string } }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const [{ result, fuel_per_round }, fuels] = await Promise.all([
    api<{ result: MixedResult; fuel_per_round: Record<string, FuelEst> }>(`/mixed-effects/${season}`),
    Promise.all([1, 2, 3, 4, 5].map(async (r) => {
      try { return [r, (await api<{ estimate: FuelEst }>(`/fuel/${season}/${r}`)).estimate] as const; }
      catch { return [r, null] as const; }
    })),
  ]);
  const drvOrder = Object.entries(result.drivers).sort((x, y) => x[1].estimate_s - y[1].estimate_s);
  const carOrder = Object.entries(result.cars).sort((x, y) => x[1].estimate_s - y[1].estimate_s);
  const carBest = carOrder[0]?.[1].estimate_s ?? 0;
  const [dev, rel] = await Promise.all([
    api<{ development: any }>(`/development/${season}`),
    api<{ reliability: any }>(`/reliability/${season}`),
  ]);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Multi-race model</div>
        <h1 className="text-xl font-semibold">Season analysis <span className="text-mute">/ {season}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Ridge mixed model across {result.n_rounds} rounds ({result.n_obs} clean laps).{" "}
          <strong className="text-warn">Model estimates.</strong> {result.identifiability}.
        </p>
      </header>

      <div className="grid gap-3 lg:grid-cols-2">
        <FadeIn>
          <section className="card overflow-x-auto">
            <h2 className="px-3 pt-3 text-sm font-medium">Car ratings (gap to best)</h2>
            <table className="w-full text-sm">
              <thead className="label text-left"><tr>
                {["Car", "Gap", "95% CI", "Width"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
              </tr></thead>
              <tbody>
                {carOrder.map(([t, r]) => (
                  <tr key={t} className="border-t border-line">
                    <td className="px-3 py-2">{t}<div className="text-[11px] text-mute">{result.team_members[t]?.join(" / ")}</div></td>
                    <td className="num px-3 py-2">{signed(r.estimate_s - carBest)} s</td>
                    <td className="num px-3 py-2 text-mute">[{signed(r.ci95_s[0] - carBest)}, {signed(r.ci95_s[1] - carBest)}]</td>
                    <td className="num px-3 py-2 text-mute">{r.ci_width_s.toFixed(3)}</td>
                  </tr>))}
              </tbody>
            </table>
          </section>
        </FadeIn>
        <FadeIn delay={0.05}>
          <section className="card overflow-x-auto">
            <h2 className="px-3 pt-3 text-sm font-medium">Driver ratings (deviation from team mean)</h2>
            <table className="w-full text-sm">
              <thead className="label text-left"><tr>
                {["Driver", "Rating", "95% CI", "Laps"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
              </tr></thead>
              <tbody>
                {drvOrder.map(([d, r]) => (
                  <tr key={d} className="border-t border-line">
                    <td className="px-3 py-2">{d}</td>
                    <td className="num px-3 py-2">{signed(r.estimate_s)} s</td>
                    <td className="num px-3 py-2 text-mute">[{signed(r.ci95_s[0])}, {signed(r.ci95_s[1])}]</td>
                    <td className="num px-3 py-2 text-mute">{result.n_laps[d] ?? "-"}</td>
                  </tr>))}
              </tbody>
            </table>
          </section>
        </FadeIn>
      </div>

      <section className="card overflow-x-auto">
        <h2 className="px-3 pt-3 text-sm font-medium">Per-circuit fuel estimates</h2>
        <table className="w-full text-sm">
          <thead className="label text-left"><tr>
            {["Round", "Fuel (s/lap)", "SE", "95% CI", "Reliable?", "Note"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
          </tr></thead>
          <tbody>
            {fuels.map(([r, f]) => (
              <tr key={r} className="border-t border-line">
                <td className="num px-3 py-2">R{r}</td>
                <td className="num px-3 py-2">{f ? f.fuel_s_per_lap.toFixed(4) : "-"}</td>
                <td className="num px-3 py-2 text-mute">{f?.se?.toFixed(4) ?? "-"}</td>
                <td className="num px-3 py-2 text-mute">{f ? `[${f.ci95[0]}, ${f.ci95[1]}]` : "-"}</td>
                <td className={`px-3 py-2 ${f?.reliable ? "text-ok" : "text-warn"}`}>{f ? (f.reliable ? "yes" : "fallback 0.035") : "-"}</td>
                <td className="px-3 py-2 text-mute">{f?.note ?? ""}</td>
              </tr>))}
          </tbody>
        </table>
        <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
          Fuel identified from multi-stint separation (tyre age resets, fuel keeps falling).
          Unreliable rounds use the 0.035 constant in the mixed model.
        </p>
      </section>

      <section className="card p-4 text-sm">
        <div className="label mb-2">Assumptions</div>
        <ul className="list-disc space-y-1 pl-5 text-mute">{result.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>

      <FadeIn>
        <section className="card p-4">
          <h2 className="mb-2 text-sm font-medium">Development curves (car gap to round-best, s)</h2>
          <DevelopmentChart development={dev.development} />
          <p className="mt-1 text-[11px] text-mute">{dev.development.note} See <Link className="underline" href="/strategy">Strategy</Link> for stint context.</p>
        </section>
      </FadeIn>

      <div className="grid gap-3 lg:grid-cols-2">
        <section className="card overflow-x-auto">
          <h2 className="px-3 pt-3 text-sm font-medium">Reliability — drivers</h2>
          <table className="w-full text-sm">
            <thead className="label text-left"><tr>
              {["Driver", "Starts", "DNFs", "Rate"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
            </tr></thead>
            <tbody>
              {rel.reliability.drivers.map((d: any) => (
                <tr key={d.driver} className="border-t border-line">
                  <td className="px-3 py-2">{d.driver} <span className="text-[11px] text-mute">{d.team}</span></td>
                  <td className="num px-3 py-2">{d.starts}</td>
                  <td className="num px-3 py-2">{d.dnfs}</td>
                  <td className="num px-3 py-2">{(d.dnf_rate * 100).toFixed(0)}%</td>
                </tr>))}
            </tbody>
          </table>
        </section>
        <section className="card overflow-x-auto">
          <h2 className="px-3 pt-3 text-sm font-medium">Reliability — teams</h2>
          <table className="w-full text-sm">
            <thead className="label text-left"><tr>
              {["Team", "Entries", "DNFs", "Rate"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
            </tr></thead>
            <tbody>
              {rel.reliability.teams.map((t: any) => (
                <tr key={t.team} className="border-t border-line">
                  <td className="px-3 py-2">{t.team}</td>
                  <td className="num px-3 py-2">{t.entries}</td>
                  <td className="num px-3 py-2">{t.dnfs}</td>
                  <td className="num px-3 py-2">{(t.dnf_rate * 100).toFixed(0)}%</td>
                </tr>))}
            </tbody>
          </table>
          <p className="border-t border-line px-3 py-2 text-[11px] text-mute">{rel.reliability.note}</p>
        </section>
      </div>
    </div>
  );
}
