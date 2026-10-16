import Link from "next/link";
import { api, EventRow, signed } from "@/lib/api";
import FadeIn from "@/components/FadeIn";

type SP = { season?: string; round?: string };
export const dynamic = "force-dynamic";

export default async function Predictions({ searchParams }: { searchParams: SP }) {
  const seasons = (await api<{ seasons: number[] }>("/seasons")).seasons;
  const season = Number(searchParams.season ?? seasons[seasons.length - 1]);
  const events = (await api<{ events: EventRow[] }>(`/events/${season}`)).events;
  const round = Number(searchParams.round ?? events[0]?.round ?? 1);
  const { result } = await api<{ result: any }>(`/predictions/${season}/${round}`);
  const rows = Object.entries<any>(result.predictions).sort(
    (x, y) => x[1].gap_to_pred_best_s - y[1].gap_to_pred_best_s);

  return (
    <div className="space-y-6">
      <header>
        <div className="label">Expected pace</div>
        <h1 className="text-xl font-semibold">Predictions <span className="text-mute">/ R{round}</span></h1>
        <p className="mt-1 max-w-3xl text-sm text-mute">
          Leave-one-round-out mixed model trained on {result.n_train_rounds} other rounds.{" "}
          <strong className="text-warn">Estimates with intervals — never certain.</strong>{" "}
          <Link className="underline" href="/methodology#prediction">Methodology</Link>.
        </p>
      </header>

      <div className="flex flex-wrap gap-1.5">
        {events.map((e) => (
          <Link key={e.round} href={`/predictions?season=${season}&round=${e.round}`}
            className={`rounded border px-2 py-1 text-xs ${e.round === round ? "border-info bg-panel2 text-ink" : "border-line text-mute"}`}>
            R{e.round}
          </Link>
        ))}
      </div>

      <FadeIn>
        <section className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="label text-left"><tr>
              {["Pred.", "Driver", "Team", "Gap to pred. best", "95% CI"].map((h) => <th key={h} className="px-3 py-2 font-normal">{h}</th>)}
            </tr></thead>
            <tbody>
              {rows.map(([d, p], i) => (
                <tr key={d} className="border-t border-line">
                  <td className="num px-3 py-2">P{i + 1}</td>
                  <td className="px-3 py-2">{d}</td>
                  <td className="px-3 py-2 text-mute">{p.team}</td>
                  <td className="num px-3 py-2">{signed(p.gap_to_pred_best_s)} s</td>
                  <td className="num px-3 py-2 text-mute">[{signed(p.ci95_s[0])}, {signed(p.ci95_s[1])}]</td>
                </tr>))}
            </tbody>
          </table>
          <p className="border-t border-line px-3 py-2 text-[11px] text-mute">
            {result.backtest_mae_s != null
              ? `Backtest MAE ${result.backtest_mae_s} s on the held-out round. ${result.backtest_note}`
              : result.backtest_note}
          </p>
        </section>
      </FadeIn>
    </div>
  );
}
