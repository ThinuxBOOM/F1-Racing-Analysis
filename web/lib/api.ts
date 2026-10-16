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
export type TeamRow = { team: string; drivers: string[]; points: number; finish_positions: (number | null)[]; n_clean: number; car_pace_s: number; gap_to_best_car_s: number; gap_ci95_s: [number | null, number | null]; n_drivers: number };
export type TyreRow = { compound: string; n_clean: number; n_drivers: number; median_fuel_corrected_s: number | null; median_tyre_age: number | null; adjusted_offset_vs_medium_s: number | null; is_reference: boolean; deg_s_per_lap: number | null; deg_se: number | null; reliable: boolean };
export type StandingDriver = { driver: string; team: string; points: number; wins: number; podiums: number; starts: number; dnfs: number };
export type StandingTeam = { team: string; points: number; wins: number; drivers: string[] };
export type CircuitInfo = { circuit: string; name: string; round: number; length_km: number | null; total_laps: number | null; avg_speed_kmh: number | null; mean_deg_s_per_lap: number | null; overtake_index: number | null; braking_zones: null; full_throttle_pct: null; telemetry_note: string };
export type TeleSample = { distance_m: number; speed: number; throttle: number; brake: boolean; gear: number; drs: number; x: number; y: number };
export type Corner = { corner: number; entry_m: number; apex_m: number; exit_m: number; entry_kmh: number; apex_kmh: number; exit_kmh: number; length_m: number; time_loss_s: number };
export type CornerDelta = { corner: number; entry_m: number; apex_m: number; exit_m: number; entry_delta_kmh: number; apex_delta_kmh: number; exit_delta_kmh: number; time_delta_s: number; a_entry_kmh: number; b_entry_kmh: number; a_apex_kmh: number; b_apex_kmh: number };
export type Rating = { estimate_s: number; ci95_s: [number, number]; ci_width_s: number };
export type MixedResult = { label: string; n_obs: number; n_rounds: number; lam: number; driver_moves_between_teams: number; identifiability: string; drivers: Record<string, Rating>; cars: Record<string, Rating>; team_members: Record<string, string[]>; n_laps: Record<string, number>; assumptions: string[] };
export type FuelEst = { fuel_s_per_lap: number; se: number | null; ci95: [number | null, number | null]; n_clean: number; n_stints: number; reliable: boolean; fallback: number; note: string };
export type VerdictItem = { rank: number; cause: string; evidence: string; confidence: string; magnitude_s: number | null };
export type StrategyRow = { driver: string; team: string; n_stops: number; pit_laps: number[]; compounds: string[]; strategy: string; n_clean: number; median_adj_pace_s: number | null; strategy_gap_to_best_s: number | null; pit_stops: { lap: number; duration_s: number | null; position_before: number | null; position_after: number | null }[] };
export type Undercut = { passer: string; rival: string; pass_lap: number; rival_pit_lap: number; before: string; after: string; kind: string };

export const f3 = (v: number | null | undefined) => (v == null ? "-" : v.toFixed(3));
export const signed = (v: number | null | undefined) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(3)}`);
export const lapFmt = (v: number | null | undefined) => {
  if (v == null) return "-";
  const m = Math.floor(v / 60); const s = (v - m * 60).toFixed(3).padStart(6, "0");
  return `${m}:${s}`;
};
