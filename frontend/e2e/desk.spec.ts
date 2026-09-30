/** UI contract tests with deterministic API fixtures. Real engine: romeo_campaign.py. */
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const state = { type: "state", t: 120, speed: 1, running: true, sim_alive: true, paused: false,
    cd_engine: "bluesky", conflicts: [], predicted: [], aircraft: [
      { id: "AFR410", type: "A320", x: -12, y: 10, lat: 49.4, lon: 3.8, hdg: 90, trk: 94,
        alt_ft: 30000, fl: 300, gs: 420, vs_fpm: 0, sel_alt_ft: 30000, cas_kt: 270, tas_kt: 440,
        lnav: true, vnav: false, route: [[20, 4]], route_names: ["TEST"], actwp: 0, conflict: false, alert: "", inzone: "" },
    ] };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path.includes("health")) body = { providers: { stt: false, llm: true, tts: false } };
    else if (path === "/api/nav") body = { waypoints: [], airports: [], fixes: [], routes: [], sector: [[-50,-40],[50,-40],[50,40],[-50,40],[-50,-40]], range_nm: 70, center: [49.25,4.05] };
    else if (path === "/api/scenarios") body = { scenarios: [{ name: "trafic_mixte", title: "Trafic mixte", description: "" }] };
    else if (path === "/api/exercise/report") { await route.fulfill({ status: 404, json: { detail: "aucun rapport" } }); return; }
    else if (path === "/api/exercise") body = { active: false };
    else if (path === "/api/sim/pause") state.paused = true;
    else if (path === "/api/sim/resume") state.paused = false;
    await route.fulfill({ json: body });
  });
  await page.routeWebSocket("**/ws", (ws) => {
    ws.send(JSON.stringify(state));
    const timer = setInterval(() => ws.send(JSON.stringify(state)), 250);
    ws.onClose(() => clearInterval(timer));
  });
  await page.goto("/");
});

test("desk controls, keyboard tabs, route data and layers remain usable", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await expect(page.getByText("Simulation en cours", { exact: true })).toBeVisible();
  await page.getByLabel("Vol AFR410, FL300, 420 nœuds", { exact: true }).click();
  await expect(page.getByText("CAS 270 / TAS 440 kt")).toBeVisible();
  await page.getByRole("button", { name: "Mettre en pause" }).click();
  await expect(page.getByRole("button", { name: "Reprendre la simulation" })).toBeEnabled();
  await page.getByRole("tab", { name: "Trafic", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Instructeur" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByLabel("Description de la situation")).toBeVisible();
  await page.getByText("Couches radar", { exact: true }).click();
  await page.getByLabel("Historique", { exact: true }).uncheck();
  await page.getByRole("tab", { name: "Débrief" }).click();
  await expect(page.getByText(/Aucun débrief disponible/)).toBeVisible();
  expect(errors).toEqual([]);
  await page.getByRole("tab", { name: "Trafic", exact: true }).click();
  await page.screenshot({ path: "test-results/desk-desktop.png", fullPage: true });
});

test("full-HD workstation keeps radar, instructor controls and radio visible together", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.getByRole("heading", { name: "Poste de contrôle" })).toBeVisible();
  await page.getByRole("tab", { name: "Instructeur" }).click();
  await expect(page.getByLabel("Scénario sauvegardé")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await expect(page.getByLabel("Clairance radio", { exact: true })).toBeVisible();
  const radio = await page.getByLabel("Clairance radio", { exact: true }).boundingBox();
  expect(radio!.y + radio!.height).toBeLessThanOrEqual(1080);
  await page.screenshot({ path: "test-results/desk-fullhd.png", fullPage: true });
});

test("failed command keeps the typed instruction and displays a useful error", async ({ page }) => {
  await page.route("**/api/command", (route) => route.fulfill({ status: 502, json: { detail: "Service LLM indisponible" } }));
  const input = page.getByLabel("Clairance radio", { exact: true });
  await input.fill("AFR410 turn heading 090");
  await page.getByRole("button", { name: "Envoyer la clairance" }).click();
  await expect(input).toHaveValue("AFR410 turn heading 090");
  await page.getByRole("tab", { name: "Journal" }).click();
  await expect(page.getByText(/Service LLM indisponible/)).toBeVisible();
});
