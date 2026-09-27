import { defineConfig } from "@playwright/test";

/** Requires ../.venv with requirements-campaign.txt; run on a compute node. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: "live.spec.ts",
  workers: 1,
  timeout: 60000,
  use: { baseURL: "http://127.0.0.1:4174", viewport: { width: 1920, height: 1080 }, trace: "retain-on-failure" },
  webServer: {
    command: "../.venv/bin/python -m uvicorn atc_app:app --app-dir ../src --host 127.0.0.1 --port 4174",
    url: "http://127.0.0.1:4174/api/state",
    timeout: 60000,
    env: { ATC_APP_NOBROWSER: "1", ATC_STT_URL: "", ATC_LLM_URL: "", ATC_TTS_URL: "",
      ATC_BLUESKY_WORKDIR: process.env.ATC_BLUESKY_WORKDIR ?? "../reports/bluesky-live-test" },
  },
});
