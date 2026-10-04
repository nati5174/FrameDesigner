/**
 * Smoke test — 1500 × 700 × 900 table at 100 kg
 *
 * Requires both servers to be running:
 *   backend:  uvicorn framegen.api:app --port 8080   (from repo root)
 *   frontend: npm run dev -- -p 3000                 (from frontend/)
 *
 * Run:  npm run test:e2e  (from frontend/)
 * Screenshots are saved to frontend/e2e/screenshots/ (gitignored).
 */

import { test, expect, Browser, BrowserContext, Page } from "@playwright/test";
import fs from "fs";
import path from "path";

const SCREENSHOT_DIR = path.join(__dirname, "screenshots");
const PROMPT = "workbench 1500 x 700 x 900 mm, holds 100 kg";

const VIEWPORTS = [
  { name: "1920x1080", width: 1920, height: 1080 },
  { name: "1280x800", width: 1280, height: 800 },
] as const;

test.beforeAll(() => {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
});

test("smoke: 1500×700×900 table at 100 kg — no errors, no overflow, badge, cut list total, cost", async ({
  browser,
}: {
  browser: Browser;
}) => {
  const allConsoleErrors: string[] = [];

  for (const vp of VIEWPORTS) {
    const context: BrowserContext = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      storageState: { cookies: [], origins: [] },
    });
    // Clear any persisted thread from a previous run
    await context.addInitScript(() => localStorage.clear());
    const page: Page = await context.newPage();

    // Collect browser-side console errors
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        allConsoleErrors.push(`[${vp.name}] ${msg.text()}`);
      }
    });

    // ── Navigate ────────────────────────────────────────────────────────────
    await page.goto("/");

    // ── Submit prompt ────────────────────────────────────────────────────────
    const input = page.getByLabel("Frame description");
    await input.fill(PROMPT);
    await input.press("Enter");

    // ── Wait for the status badge (there can be multiple: thread + side panel) ─
    // Use first() to avoid strict-mode violation; all badges show the same value.
    const badge = page.locator('[aria-label^="Load check:"]').first();
    await badge.waitFor({ timeout: 20_000 });

    // ── No horizontal overflow ────────────────────────────────────────────────
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    );
    expect(overflows, `Horizontal overflow at ${vp.name}`).toBe(false);

    // ── Status badge text is one of the three valid values ────────────────────
    const badgeLabel = await badge.getAttribute("aria-label");
    expect(
      badgeLabel,
      "aria-label must contain a known status"
    ).toMatch(/Load check: (Pass|Pass with warning|Fail)/);

    // ── Open the Cut list section (collapsed by default) ─────────────────────
    // The side panel may have multiple "Cut list" buttons (desktop + mobile sheet).
    const cutListBtn = page.getByRole("button", { name: "Cut list" }).first();
    await cutListBtn.click();

    // ── Cut list total shows a length in mm ───────────────────────────────────
    // Scope to the first visible tfoot to avoid strict-mode issues if
    // a cut list is also rendered in the thread entries.
    const firstTfoot = page.locator("tfoot").first();
    const totalCell = firstTfoot.locator("tr").first().locator("td").last();
    await expect(totalCell).toContainText("mm");
    const totalText = await totalCell.textContent();
    expect(parseInt(totalText ?? "0", 10)).toBeGreaterThan(0);

    // ── A cost is shown (not "n/a") ───────────────────────────────────────────
    const costCell = firstTfoot.locator("tr").last().locator("td").last();
    await expect(costCell).toContainText("$");

    // ── Wait for the 3D viewer canvas to appear and finish rendering ──────────
    // The viewer is a dynamic import (ssr:false) + Suspense, so it resolves
    // independently of the API response.  Wait for the canvas to mount, then
    // give WebGL (via SwiftShader) a moment to paint the first frame.
    await page.locator("canvas").waitFor({ timeout: 15_000 });
    await page.waitForTimeout(1500);

    // ── Screenshot ────────────────────────────────────────────────────────────
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, `smoke-${vp.name}.png`),
      fullPage: false,
    });

    await context.close();
  }

  // ── No console errors across all viewports ────────────────────────────────
  expect(
    allConsoleErrors,
    `Console errors:\n${allConsoleErrors.join("\n")}`
  ).toHaveLength(0);
});
