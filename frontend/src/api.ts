/** Client REST minimal vers le serveur FastAPI local. */
import type { Caps, ExerciseReport, ExerciseState, NavData, ScenarioMeta } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* texte brut */ }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

const post = <T>(url: string, body?: unknown) =>
  request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });

export const api = {
  health: () => request<{ mode: string; caps: Caps }>("/api/health"),
  healthRefresh: () => post<{ mode: string; caps: Caps }>("/api/health/refresh"),
  nav: () => request<NavData>("/api/nav"),
  scenarios: () => request<{ scenarios: ScenarioMeta[] }>("/api/scenarios"),
  generateScenario: (description: string) => post("/api/scenario", { description }),
  loadScenario: (name: string) => post("/api/scenario/load", { name }),
  command: (text: string) => post("/api/command", { text }),

  setWind: (dir: number | "", spd?: number, alt?: number) =>
    post("/api/weather/wind", { dir, spd, alt }),
  setTurbulence: (level: number) => post("/api/weather/turbulence", { level }),
  addZone: (ztype: "storm" | "restricted", x: number, y: number, r: number) =>
    post("/api/weather/zone", { ztype, shape: "CIRCLE", x, y, r }),
  clearZones: () => post("/api/weather/clearzones"),

  pause: () => post("/api/sim/pause"),
  resume: () => post("/api/sim/resume"),
  reset: () => post("/api/sim/reset"),
  setSpeed: (value: number) => post("/api/sim/speed", { value }),
  launchGui: () => post<{ ok: boolean }>("/api/gui/launch"),

  exercise: () => request<ExerciseState>("/api/exercise"),
  exerciseStart: (difficulty: string, duration_min?: number) =>
    post<ExerciseState>("/api/exercise/start", { difficulty, duration_min }),
  exerciseStop: () => post<ExerciseReport>("/api/exercise/stop"),
  exerciseReport: () => request<ExerciseReport>("/api/exercise/report"),

  voice: async (wav: Blob) => {
    const fd = new FormData();
    fd.append("file", wav, "utt.wav");
    const r = await fetch("/api/voice", { method: "POST", body: fd });
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
      throw new Error(detail);
    }
    return r.json() as Promise<{ audio_b64?: string | null }>;
  },
};
