import { afterEach, describe, expect, it, vi } from "vitest";
import { playB64Wav, WavRecorder } from "../src/audio";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("audio resource lifecycle", () => {
  it("closes a microphone acquired after recording was cancelled", async () => {
    let grant!: (stream: MediaStream) => void;
    const stop = vi.fn();
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: () => new Promise<MediaStream>((resolve) => { grant = resolve; }) } });
    const recorder = new WavRecorder();
    const starting = recorder.start();
    expect(await recorder.stop()).toBeNull();
    grant({ getTracks: () => [{ stop }] } as unknown as MediaStream);
    await starting;
    expect(stop).toHaveBeenCalledOnce();
  });

  it("releases the microphone if audio context creation fails", async () => {
    const stop = vi.fn();
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [{ stop }] }) } });
    vi.stubGlobal("AudioContext", class { constructor() { throw new Error("context unavailable"); } });
    await expect(new WavRecorder().start()).rejects.toThrow("context unavailable");
    expect(stop).toHaveBeenCalledOnce();
  });

  it("releases the audio URL and reports rejected playback", async () => {
    const revoke = vi.fn();
    vi.stubGlobal("URL", { createObjectURL: () => "blob:readback", revokeObjectURL: revoke });
    vi.stubGlobal("Audio", class { play() { return Promise.reject(new Error("playback blocked")); } });
    await expect(playB64Wav("AA==")).rejects.toThrow("playback blocked");
    expect(revoke).toHaveBeenCalledWith("blob:readback");
  });
});
