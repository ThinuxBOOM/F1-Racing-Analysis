import { api, MetricDoc } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Methodology() {
  const { metrics } = await api<{ metrics: MetricDoc[] }>("/methodology");
  const rows: [string, string][] = [["Definition", "definition"], ["How it is calculated", "calculation"], ["Data used", "data_used"], ["Limitations", "limitations"]];
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">Methodology</h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">Every metric shown in this app is documented here from the same registry the code reads, so documentation cannot drift from the calculation. Public timing data has no fuel load, engine modes, setup or tyre temperatures; anything that depends on those is an estimate and is labelled as such.</p>
      </header>
      {metrics.map((m) => (
        <section key={m.id} id={m.id} className="card scroll-mt-6 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium">{m.name}</h2>
            <span className={`rounded border px-2 py-0.5 text-[11px] uppercase ${m.status === "implemented" ? "border-ok/50 text-ok" : "border-line text-mute"}`}>{m.status}</span>
          </div>
          <dl className="mt-3 space-y-2 text-sm">
            {rows.map(([label, key]) => (
              <div key={key}><dt className="label">{label}</dt><dd className="text-ink/90">{(m as unknown as Record<string, string>)[key]}</dd></div>
            ))}
            <div><dt className="label">Needs telemetry</dt><dd>{m.needs_telemetry ? "Yes" : "No, timing data only"}</dd></div>
          </dl>
        </section>
      ))}
    </div>
  );
}
