import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSim } from "../src/useSim";

vi.mock("../src/api", () => ({ api: {
  health: vi.fn(async () => ({ providers: { stt: true, llm: true, tts: true } })),
  healthRefresh: vi.fn(async () => ({ providers: { stt: true, llm: true, tts: true } })),
  exerciseReport: vi.fn(async () => null),
} }));
vi.mock("../src/audio", () => ({ playB64Wav: vi.fn(async () => undefined) }));

class FakeSocket {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor() { FakeSocket.instances.push(this); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) }); }
  close() { this.readyState = 3; this.onclose?.(); }
}
const state = (t: number) => ({ type: "state", t, speed: 1, aircraft: [], conflicts: [], predicted: [], paused: false, running: true, sim_alive: true });

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("simulation feed lifecycle", () => {
  it("accepts the initial frame of older servers before predictions are ready", async () => {
    const { result } = renderHook(useSim);
    const socket = FakeSocket.instances[0];
    await act(async () => { socket.open(); socket.message({ ...state(0), predicted: undefined }); });
    expect(result.current.connection).toBe("connected");
    expect(result.current.state.predicted).toEqual([]);
    expect(result.current.stateRef.current.predicted).toEqual([]);
  });

  it("shows disconnection and cancels pending reconnect on unmount", async () => {
    const { result, unmount } = renderHook(useSim);
    const socket = FakeSocket.instances[0];
    await act(async () => { socket.open(); socket.message(state(1)); });
    expect(result.current.connection).toBe("connected");
    act(() => socket.close());
    expect(result.current.connection).toBe("disconnected");
    unmount();
    act(() => vi.advanceTimersByTime(10000));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("renders the final state of a burst and keeps the radar ref current", async () => {
    const { result } = renderHook(useSim);
    const socket = FakeSocket.instances[0];
    await act(async () => { socket.open(); socket.message(state(1)); socket.message(state(2)); socket.message(state(3)); });
    expect(result.current.stateRef.current.t).toBe(3);
    act(() => vi.advanceTimersByTime(260));
    expect(result.current.state.t).toBe(3);
  });

  it("reconnects if an open connection stops delivering snapshots", async () => {
    const { result } = renderHook(useSim);
    const socket = FakeSocket.instances[0];
    await act(async () => { socket.open(); socket.message(state(1)); });
    act(() => vi.advanceTimersByTime(6100));
    expect(result.current.connection).toBe("disconnected");
    act(() => vi.advanceTimersByTime(1600));
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("rejects malformed states without replacing the last valid radar state", async () => {
    const { result } = renderHook(useSim);
    const socket = FakeSocket.instances[0];
    await act(async () => { socket.open(); socket.message(state(12)); socket.message({ type: "state", t: "bad" }); });
    expect(result.current.stateRef.current.t).toBe(12);
    expect(result.current.log.some((entry) => entry.kind === "warn")).toBe(true);
  });
});
