import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

test("viewer dashboard smoke on desktop and phone", async ({
  browser,
  baseURL,
}) => {
  const shots = path.resolve("screenshots");
  await mkdir(shots, { recursive: true });
  for (const [name, viewport] of [
    ["desktop", { width: 1440, height: 1000 }],
    ["phone", { width: 390, height: 844 }],
  ] as const) {
    const context = await browser.newContext({
      viewport,
      baseURL,
      ignoreHTTPSErrors: true,
      colorScheme: "light",
    });
    const page = await context.newPage();
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/sites");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await page.screenshot({
      path: path.join(shots, `login-${name}.png`),
      fullPage: true,
    });
    await page
      .getByLabel("Email", { exact: true })
      .fill(process.env.E2E_VIEWER_EMAIL ?? "viewer@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill(process.env.E2E_VIEWER_PASSWORD ?? "viewer-smoke-test-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page).toHaveURL(/\/sites$/);
    await expect(page.getByTestId("site-card")).toHaveCount(1);
    await expect(page.getByTestId("site-card")).toContainText("Arlington");
    await expect(page.getByTestId("site-card")).not.toContainText("Site 2");
    await page.screenshot({
      path: path.join(shots, `sites-${name}.png`),
      fullPage: true,
    });
    await page.getByTestId("site-card").click();
    await expect(
      page.getByRole("heading", { name: "Overview", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Weekly report", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("img", {
        name: "Daily GSC clicks, GSC impressions, and GA4 sessions",
      }),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(shots, `overview-${name}.png`),
      fullPage: true,
    });
    await page
      .getByRole("navigation", { name: "Site sections" })
      .getByRole("link", { name: "Search", exact: true })
      .click();
    await expect(page).toHaveURL(/tab=search/);
    await expect(
      page.getByRole("heading", { name: "Search performance" }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Pages", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Queries", exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(shots, `search-${name}.png`),
      fullPage: true,
    });
    await page
      .getByRole("table", { name: "Pages", exact: true })
      .getByRole("button", { name: "Clicks" })
      .click();
    await page.getByLabel("Device", { exact: true }).selectOption("MOBILE");
    await expect(page).toHaveURL(/device=MOBILE/);
    await page
      .getByRole("navigation", { name: "Site sections" })
      .getByRole("link", { name: "Traffic", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Traffic performance" }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Traffic pages" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.goto("/sites/site2");
    await expect(
      page.getByRole("heading", { name: "Site not found", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(errors).toEqual([]);
    await context.close();
  }
});
