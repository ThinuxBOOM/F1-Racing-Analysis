// All data access goes through this file. Components never know where data comes from.
const BASE = process.env.API_URL ?? "http://localhost:8000";

export async function api<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

export type Meta = { data_source: string; is_mock: boolean; model_version: string; notice: string };
export type EventRow = { season: number; round: number; name: string; circuit: string; country: string; total_laps: number; length_km: number };
export type Consistency = { driver: string; score: number; lap_sd_s: number; sector_sd_s: number; n_clean: number; lap_score: number; sector_score: number };
export type Teammate = { teammate: string; delta_s: number | null; ci_low: number | null; ci_high: number | null; verdict: string };
export type SummaryRow = {
  driver: string; team: string; grid_pos: number | null; finish_pos: number | null; status: string | null; points: number | null;
  best_lap_s: number | null; gap_to_best_s: number | null; median_clean_pace_s: number | null; n_clean: number;
  gap_to_field_best_pace_s: number | null; best_sectors: Record<string, number | null>;
  consistency: Consistency | null; teammate: Teammate | null;
};
export type Summary = { meta: Meta; rows: SummaryRow[]; sector_leaders: Record<string, string> };
export type PaceLap = { driver: string; team: string; lap_number: number; lap_time_s: number | null; fuel_corr_time_s: number | null; compound: string | null; tyre_age: number | null; stint_number: number; position: number | null; is_clean: boolean; exclude_reason: string | null };
export type Pace = { meta: Meta; laps: PaceLap[]; field_median: { lap_number: number; field_median_s: number }[] };
export type Stint = { driver: string; stint: number; compound: string; start_lap: number; end_lap: number; start_tyre_age: number | null; n_laps: number; n_clean: number; mean_pace_s: number | null; best_lap_s: number | null; deg_s_per_lap: number | null; deg_se: number | null; reliable: boolean };
export type Interval = { estimate_s: number; ci95_s: [number, number] };
export type Decomp = {
  driver_a: string; driver_b: string; same_team: boolean; label: string; total_raw_gap_s: number;
  components: { car: Interval; driver: Interval; strategy_tyres_traffic: Interval };
  adjusted_gap_s: Interval; n_laps: { a: number; b: number }; assumptions: string[];
};
export type Quality = { drivers: { driver: string; team: string; laps_present: number; laps_clean: number; completeness: number; excluded: Record<string, number> }[]; mean_completeness: number; flags: string[] };
export type MetricDoc = { id: string; name: string; status: string; needs_telemetry: boolean; definition: string; calculation: string; data_used: string; limitations: string };

export const f3 = (v: number | null | undefined) => (v == null ? "-" : v.toFixed(3));
export const signed = (v: number | null | undefined) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(3)}`);
export const lapFmt = (v: number | null | undefined) => {
  if (v == null) return "-";
  const m = Math.floor(v / 60); const s = (v - m * 60).toFixed(3).padStart(6, "0");
  return `${m}:${s}`;
};
