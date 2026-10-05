/**
 * One-off Playwright script to capture docs/images/ screenshots.
 * Run with:  npx playwright test e2e/docs_screenshots.spec.ts
 * Requires both servers running (python scripts/dev.py from repo root).
 */

import { test, Browser, BrowserContext, Page } from "@playwright/test";
import path from "path";
import fs from "fs";

const OUT = path.join(__dirname, "..", "..", "docs", "images");

const VP = { width: 1600, height: 900 };

async function freshPage(browser: Browser): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext({
    viewport: VP,
    storageState: { cookies: [], origins: [] },
  });
  await context.addInitScript(() => localStorage.clear());
  const page = await context.newPage();
  return { context, page };
}

async function submit(page: Page, prompt: string) {
  const input = page.getByLabel("Frame description");
  await input.fill(prompt);
  await input.press("Enter");
}

async function waitForResult(page: Page) {
  // Wait for status badge and canvas
  await page.locator('[aria-label^="Load check:"]').first().waitFor({ timeout: 30_000 });
  await page.locator("canvas").waitFor({ timeout: 15_000 });
  await page.waitForTimeout(2000); // let WebGL paint
}

// ── 1. Passing workbench ───────────────────────────────────────────────────────

test("docs: passing workbench", async ({ browser }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const { context, page } = await freshPage(browser);

  await page.goto("/");
  await submit(page, "workbench 1200 x 600 x 900 mm, holds 80 kg");
  await waitForResult(page);

  await page.screenshot({ path: path.join(OUT, "pass.png") });
  await context.close();
});

// ── 2. Failing frame with suggestions ─────────────────────────────────────────

test("docs: failing frame with suggestions", async ({ browser }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const { context, page } = await freshPage(browser);

  await page.goto("/");
  // Wide bench — 3000 mm span fails the load check; suggestions appear
  await submit(page, "bench 3000 x 700 x 900 mm, holds 100 kg");
  await waitForResult(page);

  // Make sure the Suggestions section is in view (it's open by default)
  const suggestions = page.locator("section").filter({ hasText: "Suggestions" }).first();
  await suggestions.scrollIntoViewIfNeeded();

  await page.screenshot({ path: path.join(OUT, "fail.png") });
  await context.close();
});

// ── 3. Shelf unit with four levels ────────────────────────────────────────────

test("docs: shelf unit four levels", async ({ browser }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const { context, page } = await freshPage(browser);

  await page.goto("/");
  await submit(page, "shelf unit 1000 x 400 x 1800 mm, 4 levels");
  await waitForResult(page);

  await page.screenshot({ path: path.join(OUT, "shelf.png") });
  await context.close();
});
