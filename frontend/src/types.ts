/** Types partages : miroirs des payloads du serveur FastAPI (atc_app.py). */

export interface Aircraft {
  id: string;
  x: number;          // NM est, autour du centre secteur
  y: number;          // NM nord
  lat: number;
  lon: number;
  hdg: number;
  trk: number;        // route sol (effet du vent)
  alt_ft: number;
  fl: number;
  gs: number;         // vitesse sol (kt)
  vs_fpm: number;     // vitesse verticale (ft/min)
  sel_alt_ft: number | null;  // altitude autorisee (autopilote)
  type: string;
  conflict: boolean;
  alert: "" | "los" | "predicted";
  inzone: string;
  route: [number, number][];
  actwp: number;
}

export interface Predicted { pair: [string, string]; t: number; d: number }

export interface Zone {
  name: string;
  type: "storm" | "restricted";
  shape: "CIRCLE" | "POLY";
  cx?: number; cy?: number; r?: number;
  points?: [number, number][];
  color: string;
}

export interface Wind { dir: number; spd: number; alt: number | null }

export interface ExerciseScore {
  total: number; grade: string;
  separation: number; conflits: number; zones: number; radio: number;
  n_los: number; t_los_s: number;
  conflits_predits: number; conflits_resolus: number;
  n_zone: number; t_zone_s: number;
  cmd_acceptees: number; cmd_rejetees: number;
}

export interface ExerciseBrief { elapsed_s: number; remaining_s: number; score: ExerciseScore }

export interface SimState {
  t: number;
  running: boolean;
  paused: boolean;
  speed: number;
  aircraft: Aircraft[];
  conflicts: [string, string][];
  predicted: Predicted[];
  cd_engine?: string;
  wind?: Wind | null;
  turbulence?: number;
  zones?: Zone[];
  exercise?: ExerciseBrief;
}

export interface NavPoint { x: number; y: number; name: string; type?: string }

export interface NavData {
  waypoints: NavPoint[];
  airports: NavPoint[];
  fixes: NavPoint[];
  routes: [number, number][];
  sector: [number, number][];
  range_nm: number;
  center: [number, number];
}

export interface Caps { romeo: boolean; asr: boolean; llm: boolean; tts: boolean }

export interface Order { callsign: string; action: string; value?: number; wpt?: string }

export interface Exchange {
  transcript: string;
  orders: Order[];
  trafscript: string[];
  rejected: string[];
  readback: string;
}

export interface ExerciseState {
  active: boolean;
  label?: string;
  difficulty?: string;
  duration_s?: number;
  elapsed_s?: number;
  remaining_s?: number;
  objectives?: string[];
  aircraft?: string[];
  conflicts_built?: { pair: [string, string]; fl: number; t_cross_s: number }[];
  wind?: Wind | null;
  storm?: { x: number; y: number; r: number } | null;
  turbulence?: number;
  mode_ia?: string;
  score?: ExerciseScore;
  last_report?: boolean;
}

export interface ExerciseReport extends Omit<ExerciseState, "score" | "active"> {
  ended_iso: string;
  started_iso: string;
  auto_ended: boolean;
  elapsed_s: number;
  score: ExerciseScore;
  minsep_series: [number, number | null][];
  los_events: { pair: string[]; t_start: number; t_end: number; min_nm: number | null }[];
  predicted_events: { pair: string[]; t_first: number; d_min: number | null }[];
  zone_events: { callsign: string; zone: string; t_start: number; t_end: number }[];
  commands: { t: number; text: string; accepted: number; rejected: number }[];
}

export interface LogEntry {
  id: number;
  t: string;             // horodatage local hh:mm:ss
  kind: "info" | "tx" | "cmd" | "pilot" | "rej" | "warn" | "ok";
  text: string;
}

export interface ScenarioMeta { name: string; title: string; description: string }

export type PlaceMode = "storm" | "restricted" | null;
