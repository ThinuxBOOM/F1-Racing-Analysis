import Link from "next/link";
import { api, Pace, Quality, Stint, Summary, f3, lapFmt, signed } from "@/lib/api";
import ScatterByCompound from "@/components/ScatterByCompound";

type SP = { season?: string; round?: string; kind?: string };

export const dynamic = "force-dynamic";

export default async function DriverPage({ params, searchParams }: { params: { code: string }; searchParams: SP }) {
  const season = Number(searchParams.season ?? 2099);
  const round = Number(searchParams.round ?? 1);
  const kind = searchParams.kind === "Q" ? "Q" : "R";
  const q = `${season}/${round}/${kind}`;
  const [sum, pace, st, qual] = await Promise.all([
    api<Summary>(`/summary/${q}`), api<Pace>(`/pace/${q}`),
    api<{ stints: Stint[] }>(`/stints/${q}`), api<{ report: Quality }>(`/quality/${q}`),
  ]);
  const row = sum.rows.find((r) => r.driver === params.code);
  if (!row) return <div className="card p-6 text-sm">No data for {params.code} in this session.</div>;
  const stints = st.stints.filter((s) => s.driver === params.code);
  const laps = pace.laps.filter((l) => l.driver === params.code && l.is_clean && l.fuel_corr_time_s != null)
    .map((l) => ({ lap: l.lap_number, t: l.fuel_corr_time_s as number, compound: l.compound ?? "?" }));
  const dq = qual.report.drivers.find((d) => d.driver === params.code);
  const c = row.consistency;

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Driver performance analysis</div>
        <h1 className="text-xl font-semibold">{row.driver} <span className="text-mute">/ {row.team}</span></h1>
        <p className="mt-1 text-sm text-mute">Round {round}, {kind === "R" ? "Race" : "Qualifying"}. <Link className="underline" href={`/?season=${season}&round=${round}&kind=${kind}`}>Back to dashboard</Link></p>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Finish / grid" value={`P${row.finish_pos ?? "-"} / P${row.grid_pos ?? "-"}`} sub={row.status ?? ""} />
        <Stat label="Median clean pace (raw)" value={lapFmt(row.median_clean_pace_s)} sub={`${row.n_clean} clean laps; tyre-adjusted gap to best: ${signed(row.gap_to_field_best_pace_s)} s`} />
        <Stat label="Consistency" value={c ? `${c.score.toFixed(0)} / 100` : "-"} sub={c ? `lap SD ${c.lap_sd_s}s, sector SD ${c.sector_sd_s}s` : "needs race data"} help="consistency" />
        {/* single-session consistency is noisy; see note below */}
        <Stat label="vs teammate" value={signed(row.teammate?.delta_s)} sub={row.teammate ? `${row.teammate.teammate}, CI [${signed(row.teammate.ci_low)}, ${signed(row.teammate.ci_high)}]` : ""} help="teammate_delta" />
      </section>
      {row.teammate && <p className="text-sm text-mute">{row.teammate.verdict}</p>}
      {c && <p className="text-[11px] text-mute">Consistency is field-relative and noisy for a single session (about ±16 points in synthetic tests). Prefer multi-race averages.</p>}

      <section className="card p-4">
        <h2 className="mb-3 text-sm font-medium">Fuel-corrected clean laps by compound</h2>
        <ScatterByCompound laps={laps} />
      </section>

      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="label text-left"><tr>
            {["Stint", "Compound", "Laps", "Clean", "Mean pace", "Best lap", "Degradation (s/lap)", "Reliable?"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
          </tr></thead>
          <tbody>{stints.map((s) => (
            <tr key={s.stint} className="border-t border-line">
              <td className="num px-3 py-2">{s.stint}</td><td className="px-3 py-2">{s.compound}</td>
              <td className="num px-3 py-2">{s.start_lap}-{s.end_lap}</td><td className="num px-3 py-2">{s.n_clean}</td>
              <td className="num px-3 py-2">{lapFmt(s.mean_pace_s)}</td><td className="num px-3 py-2">{lapFmt(s.best_lap_s)}</td>
              <td className="num px-3 py-2">{s.deg_s_per_lap == null ? "-" : `${signed(s.deg_s_per_lap)} ± ${f3(s.deg_se)}`}</td>
              <td className={`px-3 py-2 ${s.reliable ? "text-ok" : "text-warn"}`}>{s.reliable ? "yes" : "low sample"}</td>
            </tr>))}</tbody>
        </table>
        <p className="border-t border-line px-3 py-2 text-[11px] text-mute">Degradation = slope of fuel-corrected clean lap time against tyre age (± 1 standard error). Short stints give unreliable slopes and are flagged.</p>
      </section>

      {dq && (
        <section className="card p-4 text-sm">
          <h2 className="mb-2 text-sm font-medium">Data quality</h2>
          <p className="text-mute">{dq.laps_clean} of {dq.laps_present} laps usable ({(dq.completeness * 100).toFixed(0)}%). Excluded: {Object.entries(dq.excluded).map(([k, v]) => `${v} ${k}`).join(", ") || "none"}.</p>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, sub, help }: { label: string; value: string; sub?: string; help?: string }) {
  return (
    <div className="card p-3">
      <div className="label flex justify-between"><span>{label}</span>{help && <Link href={`/methodology#${help}`} className="normal-case text-info">how?</Link>}</div>
      <div className="num mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-0.5 text-xs text-mute">{sub}</div>
    </div>
  );
}
