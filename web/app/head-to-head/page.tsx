import Link from "next/link";
import { api, Decomp, EventRow, Summary, signed } from "@/lib/api";
import DecompBars from "@/components/DecompBars";

type SP = { season?: string; round?: string; a?: string; b?: string };

export const dynamic = "force-dynamic";

export default async function HeadToHead({ searchParams }: { searchParams: SP }) {
  const season = Number(searchParams.season ?? 2099);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const sum = await api<Summary>(`/summary/${season}/${round}/R`);
  const codes = sum.rows.map((r) => r.driver);
  const a = searchParams.a && codes.includes(searchParams.a) ? searchParams.a : codes[0];
  const b = searchParams.b && codes.includes(searchParams.b) ? searchParams.b : codes[codes.length - 1];
  const res = a !== b ? await api<{ result: Decomp }>(`/driver-vs-car/${season}/${round}/${a}/${b}`) : null;
  const d = res?.result;

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Driver vs machine</div>
        <h1 className="text-xl font-semibold">Head-to-head</h1>
        <p className="mt-1 text-sm text-mute">Splits the pace gap into car, driver and circumstance. <strong className="text-warn">Model estimate</strong>, not measured fact.</p>
      </header>

      <form className="flex flex-wrap items-end gap-3" action="/head-to-head">
        <input type="hidden" name="season" value={season} />
        <Pick name="round" label="Grand Prix" value={String(round)} opts={events.map((e) => [String(e.round), `R${e.round} ${e.name}`])} />
        <Pick name="a" label="Driver A" value={a} opts={codes.map((c) => [c, c])} />
        <Pick name="b" label="Driver B" value={b} opts={codes.map((c) => [c, c])} />
        <button className="rounded border border-line bg-panel2 px-3 py-1.5 text-sm hover:border-info">Compare</button>
      </form>

      {!d ? <div className="card p-4 text-sm text-mute">Pick two different drivers.</div> : (
        <>
          <section className="card p-4">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-sm font-medium">{d.driver_a} vs {d.driver_b}{d.same_team && <span className="ml-2 text-xs text-mute">(teammates: car part is zero by construction)</span>}</h2>
              <div className="num text-sm">Observed gap <strong>{signed(d.total_raw_gap_s)} s</strong> <span className="text-mute">| model-adjusted {signed(d.adjusted_gap_s.estimate_s)} [{signed(d.adjusted_gap_s.ci95_s[0])}, {signed(d.adjusted_gap_s.ci95_s[1])}]</span></div>
            </div>
            <DecompBars d={d} />
          </section>
          <section className="card p-4 text-sm">
            <div className="label mb-2">Assumptions behind this estimate</div>
            <ul className="list-disc space-y-1 pl-5 text-mute">{d.assumptions.map((x) => <li key={x}>{x}</li>)}</ul>
            <p className="mt-3 text-[11px] text-mute">Based on {d.n_laps.a} and {d.n_laps.b} clean laps. Full method: <Link className="underline" href="/methodology#driver_vs_car">Methodology</Link>.</p>
          </section>
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
