/** Scope radar interactif : rendu canvas 60 fps, zoom molette, pan a la souris,
 *  selection d'un aeronef au clic, placement de zones meteo. */
import { useEffect, useRef } from "react";
import type { NavData, PlaceMode, SimState } from "../types";
import { drawScope, drawWindArrow, sx, sy, toNm, type View, type RadarOptions } from "../radar";

const TRAIL_LEN = 14;

interface Props {
  stateRef: React.RefObject<SimState>;
  nav: NavData;
  selected: string | null;
  onSelect: (id: string | null) => void;
  placeMode: PlaceMode;
  onPlace: (x: number, y: number) => void;
  options: RadarOptions;
  /** centre la vue sur cet avion quand la valeur change */
  centerOn?: { id: string; tick: number } | null;
}

export default function RadarCanvas({
  stateRef, nav, selected, onSelect, placeMode, onPlace, options, centerOn,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const viewRef = useRef({ panX: 0, panY: 0, zoom: 1 });
  const trailsRef = useRef(new Map<string, [number, number][]>());
  const propsRef = useRef({ selected, placeMode, options, nav, onSelect, onPlace });
  propsRef.current = { selected, placeMode, options, nav, onSelect, onPlace };

  // recentrage demande depuis les strips
  useEffect(() => {
    if (!centerOn) return;
    const a = stateRef.current?.aircraft.find((x) => x.id === centerOn.id);
    if (a) {
      viewRef.current.panX = a.x;
      viewRef.current.panY = a.y;
      if (viewRef.current.zoom < 1.6) viewRef.current.zoom = 1.6;
    }
  }, [centerOn, stateRef]);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    let sweep = 0;
    let lastTs = 0;
    let lastSimT = -1;
    let lastPaint: unknown[] = [];
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const makeView = (): View => {
      const w = canvas.clientWidth, h = canvas.clientHeight;
      const { panX, panY, zoom } = viewRef.current;
      const base = Math.max(1, Math.min(w, h) / 2 - 30) / (propsRef.current.nav.range_nm * 1.05 || 70);
      return { panX, panY, scale: base * zoom, w, h };
    };

    const resize = () => {
      const r = canvas.parentElement!.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(r.width * dpr);
      canvas.height = Math.floor(r.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      lastPaint = []; // Resizing clears the bitmap, including a change of display DPR.
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement!);

    const render = (ts: number) => {
      const st = stateRef.current;
      const dt = lastTs ? (ts - lastTs) / 1000 : 0;
      lastTs = ts;
      if (st && !st.paused) sweep = (sweep + dt * 40) % 360;

      // traines : un echo par tick simulateur
      if (st && st.t !== lastSimT) {
        if (st.t < lastSimT) trailsRef.current.clear();
        lastSimT = st.t;
        const seen = new Set<string>();
        for (const a of st.aircraft) {
          seen.add(a.id);
          const tr = trailsRef.current.get(a.id) ?? [];
          tr.push([a.x, a.y]);
          if (tr.length > TRAIL_LEN) tr.shift();
          trailsRef.current.set(a.id, tr);
        }
        for (const id of trailsRef.current.keys()) if (!seen.has(id)) trailsRef.current.delete(id);
      }

      const v = makeView();
      const p = propsRef.current;
      const signature = [st, p.nav, p.options, p.selected, v.panX, v.panY, v.scale, v.w, v.h];
      const animateSweep = p.options.sweep && !reducedMotion && !st.paused;
      if (st && (animateSweep || signature.some((value, i) => value !== lastPaint[i]))) {
        lastPaint = signature;
        drawScope(ctx, v, propsRef.current.nav, st, trailsRef.current,
          propsRef.current.selected, sweep,
          { ...propsRef.current.options, sweep: propsRef.current.options.sweep && !reducedMotion });
        drawWindArrow(ctx, v, st);
      }
      raf = requestAnimationFrame(render);
    };
    raf = requestAnimationFrame(render);

    /* ---- interactions ---- */
    let drag: { x: number; y: number; panX: number; panY: number; moved: boolean } | null = null;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const v = makeView();
      const [mx, my] = toNm(v, e.offsetX, e.offsetY);
      const f = e.deltaY < 0 ? 1.18 : 1 / 1.18;
      const z = Math.min(12, Math.max(0.4, viewRef.current.zoom * f));
      const k = viewRef.current.zoom / z;
      // garde le point sous le curseur immobile
      viewRef.current.panX = mx - (mx - viewRef.current.panX) * k;
      viewRef.current.panY = my - (my - viewRef.current.panY) * k;
      viewRef.current.zoom = z;
    };

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, panX: viewRef.current.panX, panY: viewRef.current.panY, moved: false };
      canvas.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.hypot(dx, dy) > 4) drag.moved = true;
      if (drag.moved) {
        const v = makeView();
        viewRef.current.panX = drag.panX - dx / v.scale;
        viewRef.current.panY = drag.panY + dy / v.scale;
      }
    };
    const onUp = (e: PointerEvent) => {
      if (e.button !== 0 || !drag) return;
      const wasDrag = drag?.moved;
      drag = null;
      // pointerup synthetique / capture deja perdue : releasePointerCapture
      // leverait NotFoundError et casserait la selection au clic
      try { canvas.releasePointerCapture(e.pointerId); } catch { /* deja relachee */ }
      if (wasDrag) return;
      // clic simple : placement de zone ou selection d'avion
      const v = makeView();
      const rect = canvas.getBoundingClientRect();
      const px = e.clientX - rect.left, py = e.clientY - rect.top;
      if (propsRef.current.placeMode) {
        const [nx, ny] = toNm(v, px, py);
        propsRef.current.onPlace(nx, ny);
        return;
      }
      const st = stateRef.current;
      let best: { id: string; d: number } | null = null;
      for (const a of st?.aircraft ?? []) {
        const d = Math.hypot(sx(v, a.x) - px, sy(v, a.y) - py);
        if (d < 16 && (!best || d < best.d)) best = { id: a.id, d };
      }
      propsRef.current.onSelect(best ? best.id : null);
    };
    const onDbl = () => { viewRef.current = { panX: 0, panY: 0, zoom: 1 }; };
    const onCancel = () => { drag = null; };
    const onKey = (e: KeyboardEvent) => {
      const v = viewRef.current;
      const step = 8 / v.zoom;
      if (e.key === "Home") onDbl();
      else if (e.key === "ArrowLeft") v.panX -= step;
      else if (e.key === "ArrowRight") v.panX += step;
      else if (e.key === "ArrowUp") v.panY += step;
      else if (e.key === "ArrowDown") v.panY -= step;
      else if (e.key === "+" || e.key === "=") v.zoom = Math.min(12, v.zoom * 1.18);
      else if (e.key === "-") v.zoom = Math.max(0.4, v.zoom / 1.18);
      else return;
      e.preventDefault();
    };

    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("dblclick", onDbl);
    canvas.addEventListener("pointercancel", onCancel);
    canvas.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("dblclick", onDbl);
      canvas.removeEventListener("pointercancel", onCancel);
      canvas.removeEventListener("keydown", onKey);
    };
  }, [stateRef]);

  return (
    <canvas
      ref={canvasRef}
      tabIndex={0}
      aria-label="Radar interactif. Les aéronefs sont aussi accessibles dans le panneau Trafic."
      aria-describedby="radar-help"
      style={{ touchAction: "none" }}
      className={`block h-full w-full ${placeMode ? "cursor-crosshair" : "cursor-default"}`}
    />
  );
}
