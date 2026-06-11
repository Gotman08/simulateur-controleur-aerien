/** Rendu du scope radar (canvas 2D) : fonctions pures de dessin.
 *  Repere : x = NM est, y = NM nord autour du centre secteur ; l'ecran est
 *  obtenu par la vue (pan en NM + zoom en px/NM). */
import type { Aircraft, NavData, SimState } from "./types";

export interface View {
  panX: number;        // decalage du centre vue, en NM
  panY: number;
  scale: number;       // px par NM
  w: number;           // taille CSS du canvas
  h: number;
}

export interface RadarOptions {
  sweep: boolean;
  labels: boolean;
  trails: boolean;
  rings: boolean;
}

const C = {
  bg: "#05080d",
  grid: "#13314a",
  gridText: "#2d5a7a",
  sector: "#3a72c4",
  route: "#173c54",
  wpt: "#4f8fe8",
  fix: "#3fc6d6",
  apt: "#caa54e",
  ok: "#38d97f",
  warn: "#ffb454",
  dang: "#ff5868",
  sel: "#9ad9ff",
  fms: "#8f7bff",
  wind: "#69d0ff",
};

export const colorOf = (a: Aircraft) =>
  a.alert === "los" ? C.dang : a.alert === "predicted" ? C.warn : C.ok;

export const sx = (v: View, x: number) => v.w / 2 + (x - v.panX) * v.scale;
export const sy = (v: View, y: number) => v.h / 2 - (y - v.panY) * v.scale;
export const toNm = (v: View, px: number, py: number): [number, number] => [
  (px - v.w / 2) / v.scale + v.panX,
  -(py - v.h / 2) / v.scale + v.panY,
];

export function drawScope(
  ctx: CanvasRenderingContext2D,
  v: View,
  nav: NavData,
  st: SimState,
  trails: Map<string, [number, number][]>,
  selected: string | null,
  sweepDeg: number,
  opt: RadarOptions,
) {
  ctx.clearRect(0, 0, v.w, v.h);
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, v.w, v.h);
  ctx.font = "11px Consolas, monospace";
  ctx.textBaseline = "alphabetic";

  if (opt.rings) drawRings(ctx, v, nav.range_nm);
  drawSector(ctx, v, nav.sector);
  drawRoutes(ctx, v, nav);
  drawWaypoints(ctx, v, nav);
  drawZones(ctx, v, st);
  drawFmsRoutes(ctx, v, st);
  if (opt.sweep) drawSweep(ctx, v, nav.range_nm, sweepDeg);
  drawConflictLines(ctx, v, st);
  for (const a of st.aircraft ?? [])
    drawAircraft(ctx, v, a, trails.get(a.id) ?? [], a.id === selected, opt);
  drawCenterMark(ctx, v);
}

function drawRings(ctx: CanvasRenderingContext2D, v: View, range: number) {
  // pas adaptatif : ~80 px entre anneaux
  const step = [5, 10, 20, 40].find((s) => s * v.scale > 70) ?? 80;
  ctx.strokeStyle = C.grid;
  ctx.fillStyle = C.gridText;
  ctx.lineWidth = 1;
  const cx = sx(v, 0), cy = sy(v, 0);
  for (let r = step; r <= Math.max(range, 80) + step; r += step) {
    ctx.beginPath();
    ctx.arc(cx, cy, r * v.scale, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.fillText(`${r}`, cx + 4, cy - r * v.scale - 3);
  }
  // graduations de cap tous les 30 degres sur l'anneau exterieur
  const R = range * v.scale;
  for (let deg = 0; deg < 360; deg += 30) {
    const a = ((90 - deg) * Math.PI) / 180;
    ctx.beginPath();
    ctx.moveTo(cx + (R - 6) * Math.cos(a), cy - (R - 6) * Math.sin(a));
    ctx.lineTo(cx + R * Math.cos(a), cy - R * Math.sin(a));
    ctx.stroke();
    ctx.fillText(String(deg).padStart(3, "0"),
      cx + (R + 14) * Math.cos(a) - 9, cy - (R + 14) * Math.sin(a) + 4);
  }
}

function drawSector(ctx: CanvasRenderingContext2D, v: View, sector: [number, number][]) {
  if (!sector?.length) return;
  ctx.save();
  ctx.strokeStyle = C.sector;
  ctx.globalAlpha = 0.55;
  ctx.lineWidth = 1.2;
  ctx.setLineDash([7, 6]);
  ctx.beginPath();
  sector.forEach((p, i) => (i ? ctx.lineTo(sx(v, p[0]), sy(v, p[1])) : ctx.moveTo(sx(v, p[0]), sy(v, p[1]))));
  ctx.stroke();
  ctx.restore();
}

function drawRoutes(ctx: CanvasRenderingContext2D, v: View, nav: NavData) {
  ctx.strokeStyle = C.route;
  ctx.lineWidth = 0.8;
  for (const [i, j] of nav.routes ?? []) {
    const a = nav.waypoints[i], b = nav.waypoints[j];
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(sx(v, a.x), sy(v, a.y));
    ctx.lineTo(sx(v, b.x), sy(v, b.y));
    ctx.stroke();
  }
}

function drawWaypoints(ctx: CanvasRenderingContext2D, v: View, nav: NavData) {
  ctx.font = "9.5px Consolas, monospace";
  ctx.lineWidth = 1;
  for (const w of nav.waypoints ?? []) {
    const x = sx(v, w.x), y = sy(v, w.y);
    ctx.strokeStyle = C.wpt;
    ctx.fillStyle = C.wpt;
    ctx.globalAlpha = 0.8;
    tri(ctx, x, y, 3.5);
    ctx.globalAlpha = 0.6;
    ctx.fillText(w.name, x + 5, y + 3);
    ctx.globalAlpha = 1;
  }
  ctx.font = "10px Consolas, monospace";
  for (const f of nav.fixes ?? []) {
    const x = sx(v, f.x), y = sy(v, f.y);
    ctx.strokeStyle = C.fix;
    ctx.fillStyle = C.fix;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x - 4, y); ctx.lineTo(x, y - 4); ctx.lineTo(x + 4, y); ctx.lineTo(x, y + 4);
    ctx.closePath();
    ctx.stroke();
    ctx.fillText(f.name, x + 6, y - 4);
  }
  ctx.font = "bold 10.5px Consolas, monospace";
  for (const p of nav.airports ?? []) {
    const x = sx(v, p.x), y = sy(v, p.y);
    ctx.strokeStyle = C.apt;
    ctx.fillStyle = C.apt;
    ctx.lineWidth = 1.2;
    ctx.strokeRect(x - 4, y - 4, 8, 8);
    ctx.fillText(p.name, x + 6, y - 4);
  }
}

function drawZones(ctx: CanvasRenderingContext2D, v: View, st: SimState) {
  for (const z of st.zones ?? []) {
    ctx.save();
    ctx.strokeStyle = z.color;
    ctx.fillStyle = z.color + "22";
    ctx.lineWidth = 1.4;
    if (z.shape === "CIRCLE" && z.cx != null && z.cy != null && z.r != null) {
      const x = sx(v, z.cx), y = sy(v, z.cy), r = z.r * v.scale;
      // hachures meteo (cellule orageuse) / liseret zone interdite
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fill(); ctx.stroke();
      ctx.fillStyle = z.color;
      ctx.font = "10px Consolas, monospace";
      ctx.fillText(z.type === "storm" ? "CB" : "P-ZONE", x - 12, y + 3);
    } else if (z.points?.length) {
      ctx.beginPath();
      z.points.forEach((p, i) => (i ? ctx.lineTo(sx(v, p[0]), sy(v, p[1])) : ctx.moveTo(sx(v, p[0]), sy(v, p[1]))));
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }
}

function drawFmsRoutes(ctx: CanvasRenderingContext2D, v: View, st: SimState) {
  ctx.save();
  for (const a of st.aircraft ?? []) {
    const r = a.route ?? [];
    if (!r.length) continue;
    ctx.strokeStyle = C.fms;
    ctx.lineWidth = 0.9;
    ctx.setLineDash([2, 4]);
    ctx.beginPath();
    ctx.moveTo(sx(v, a.x), sy(v, a.y));
    for (const p of r) ctx.lineTo(sx(v, p[0]), sy(v, p[1]));
    ctx.stroke();
    ctx.setLineDash([]);
    if (a.actwp >= 0 && a.actwp < r.length) {
      const w = r[a.actwp];
      ctx.strokeStyle = C.fms;
      ctx.beginPath();
      ctx.arc(sx(v, w[0]), sy(v, w[1]), 3, 0, 2 * Math.PI);
      ctx.stroke();
    }
  }
  ctx.restore();
}

function drawSweep(ctx: CanvasRenderingContext2D, v: View, range: number, deg: number) {
  const cx = sx(v, 0), cy = sy(v, 0), R = range * v.scale;
  ctx.save();
  for (let k = 16; k >= 0; k--) {
    const a = ((90 - (deg - k * 2.2)) * Math.PI) / 180;
    ctx.strokeStyle = C.ok;
    ctx.globalAlpha = k === 0 ? 0.5 : Math.max(0, 0.12 - k * 0.007);
    ctx.lineWidth = k === 0 ? 1.2 : 1.6;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + R * Math.cos(a), cy - R * Math.sin(a));
    ctx.stroke();
  }
  ctx.restore();
}

function drawConflictLines(ctx: CanvasRenderingContext2D, v: View, st: SimState) {
  const pos = new Map((st.aircraft ?? []).map((a) => [a.id, a]));
  for (const pair of st.conflicts ?? []) {
    const a = pos.get(pair[0]), b = pos.get(pair[1]);
    if (!a || !b) continue;
    ctx.strokeStyle = C.dang;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(sx(v, a.x), sy(v, a.y));
    ctx.lineTo(sx(v, b.x), sy(v, b.y));
    ctx.stroke();
  }
  for (const p of st.predicted ?? []) {
    const a = pos.get(p.pair[0]), b = pos.get(p.pair[1]);
    if (!a || !b) continue;
    ctx.save();
    ctx.strokeStyle = C.warn;
    ctx.lineWidth = 1.1;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(sx(v, a.x), sy(v, a.y));
    ctx.lineTo(sx(v, b.x), sy(v, b.y));
    ctx.stroke();
    ctx.restore();
    ctx.fillStyle = C.warn;
    ctx.font = "10px Consolas, monospace";
    ctx.fillText(`${p.t}s · ${p.d} NM`,
      (sx(v, a.x) + sx(v, b.x)) / 2 + 4, (sy(v, a.y) + sy(v, b.y)) / 2 - 4);
  }
}

function drawAircraft(
  ctx: CanvasRenderingContext2D,
  v: View,
  a: Aircraft,
  trail: [number, number][],
  isSel: boolean,
  opt: RadarOptions,
) {
  const col = colorOf(a);
  const x = sx(v, a.x), y = sy(v, a.y);

  if (opt.trails) {
    ctx.fillStyle = col;
    trail.forEach(([tx, ty], i) => {
      ctx.globalAlpha = 0.06 + (0.3 * i) / Math.max(1, trail.length);
      ctx.fillRect(sx(v, tx) - 1.5, sy(v, ty) - 1.5, 3, 3);
    });
    ctx.globalAlpha = 1;
  }

  // vecteur vitesse : projection a 1 minute (gs / 60 NM)
  const lead = (a.gs / 60) * v.scale;
  const ah = ((90 - (a.trk ?? a.hdg)) * Math.PI) / 180;
  ctx.strokeStyle = col;
  ctx.lineWidth = 1.1;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + lead * Math.cos(ah), y - lead * Math.sin(ah));
  ctx.stroke();

  // blip
  ctx.lineWidth = 1.7;
  ctx.strokeRect(x - 4, y - 4, 8, 8);
  if (a.inzone) {
    ctx.strokeStyle = C.fms;
    ctx.strokeStyle = "#ff5ab0";
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(x, y, 10, 0, 2 * Math.PI); ctx.stroke();
  }
  if (isSel) {
    ctx.strokeStyle = C.sel;
    ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.arc(x, y, 13, 0, 2 * Math.PI); ctx.stroke();
  }

  if (!opt.labels) return;
  // bloc de donnees : CS / FL(tendance)CFL / GS — ligne d'attache + fond
  const lx = x + 14, ly = y - 22;
  const trend = a.vs_fpm > 300 ? "↑" : a.vs_fpm < -300 ? "↓" : "";
  const cfl = a.sel_alt_ft != null && Math.abs(a.sel_alt_ft - a.alt_ft) > 200
    ? String(Math.round(a.sel_alt_ft / 100)).padStart(3, "0") : "";
  const l1 = a.id;
  const l2 = `${String(a.fl).padStart(3, "0")}${trend}${cfl ? " " + cfl : ""} ${String(a.gs).padStart(3, "0")}`;
  ctx.font = "11px Consolas, monospace";
  const wd = Math.max(ctx.measureText(l1).width, ctx.measureText(l2).width);
  ctx.strokeStyle = col;
  ctx.globalAlpha = 0.5;
  ctx.lineWidth = 0.8;
  ctx.beginPath(); ctx.moveTo(x + 5, y - 5); ctx.lineTo(lx - 2, ly + 12); ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.fillStyle = "rgba(5,8,13,0.72)";
  ctx.fillRect(lx - 3, ly - 10, wd + 7, 26);
  ctx.fillStyle = isSel ? C.sel : col;
  ctx.fillText(l1, lx, ly);
  ctx.fillText(l2, lx, ly + 12);
}

function drawCenterMark(ctx: CanvasRenderingContext2D, v: View) {
  const x = sx(v, 0), y = sy(v, 0);
  ctx.strokeStyle = C.ok;
  ctx.lineWidth = 1.1;
  ctx.beginPath();
  ctx.moveTo(x - 6, y); ctx.lineTo(x + 6, y);
  ctx.moveTo(x, y - 6); ctx.lineTo(x, y + 6);
  ctx.stroke();
}

export function drawWindArrow(ctx: CanvasRenderingContext2D, v: View, st: SimState) {
  const w = st.wind;
  if (!w) return;
  const ox = 60, oy = v.h - 52, len = 24;
  const a = ((90 - (w.dir + 180)) * Math.PI) / 180;   // fleche orientee "vers ou va" le vent
  ctx.save();
  ctx.strokeStyle = C.wind;
  ctx.fillStyle = C.wind;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(ox, oy);
  ctx.lineTo(ox + len * Math.cos(a), oy - len * Math.sin(a));
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(ox + len * Math.cos(a), oy - len * Math.sin(a), 2.5, 0, 2 * Math.PI);
  ctx.fill();
  ctx.font = "11px Consolas, monospace";
  ctx.fillText(
    `VENT ${String(w.dir).padStart(3, "0")}/${w.spd} kt${w.alt ? " FL" + Math.round(w.alt / 100) : ""}`,
    ox - 32, oy + 18);
  ctx.restore();
}

function tri(ctx: CanvasRenderingContext2D, x: number, y: number, s: number) {
  ctx.beginPath();
  ctx.moveTo(x, y - s);
  ctx.lineTo(x - s, y + s);
  ctx.lineTo(x + s, y + s);
  ctx.closePath();
  ctx.stroke();
}
