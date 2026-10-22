import { expect, test, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const axes = [
  "impressions-clicks",
  "funnel",
  "devices",
  "geography",
  "sitemaps",
  "internal-links",
  "site-links",
  "search-requests",
];
async function login(page: Page) {
  await page.goto("/login");
  await page
    .getByLabel("Email", { exact: true })
    .fill(process.env.E2E_ADMIN_EMAIL ?? "admin@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env.E2E_ADMIN_PASSWORD ?? "admin-smoke-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/sites$/);
}

test("all analysis axes render charts or setup states at desktop and phone widths", async ({
  browser,
  baseURL,
}) => {
  const shots = path.resolve("screenshots/analysis");
  await mkdir(shots, { recursive: true });
  for (const [name, viewport, colorScheme] of [
    ["desktop", { width: 1440, height: 1000 }, "light"],
    ["phone", { width: 390, height: 844 }, "light"],
    ["phone-dark", { width: 390, height: 844 }, "dark"],
  ] as const) {
    const context = await browser.newContext({
      baseURL,
      viewport,
      colorScheme,
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await login(page);
    await page.goto("/sites/arlington?tab=analysis");
    await expect(
      page.getByRole("heading", { name: "Analysis", exact: true }),
    ).toBeVisible();
    for (const axis of axes) {
      const section = page.getByTestId(`axis-${axis}`);
      await section.scrollIntoViewIfNeeded();
      await expect(section.getByRole("heading", { level: 3 })).toBeVisible();
      await expect(
        section
          .locator('[data-testid="axis-chart"], [data-testid="axis-empty"]')
          .first(),
      ).toBeVisible();
      await expect(section.locator(".badge")).toBeVisible();
      await expect(section.locator(".axis-finding")).not.toBeEmpty();
      expect(
        await section
          .locator(".axis-chart svg, .axis-heatmap, .axis-empty")
          .count(),
      ).toBeGreaterThan(0);
    }
    await expect(page.getByTestId("axis-funnel")).toContainText(
      "Not tracked yet",
    );
    await expect(page.getByTestId("axis-geography")).toContainText(
      "Configure your service cities",
    );
    await expect(page.getByTestId("axis-search-requests")).toContainText(
      "Needs keyword provider",
    );
    await expect(page.locator(".heat-cell")).toHaveCount(25);
    await expect(page.getByTestId("axis-sitemaps")).toContainText(
      "Excluded by noindex",
    );
    await expect(page.getByTestId("axis-devices")).toContainText("site-level");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: path.join(shots, `${name}.png`),
      fullPage: true,
    });
    // A focused phone crop makes labels and table containment reviewable too.
    await page
      .getByTestId("axis-impressions-clicks")
      .screenshot({ path: path.join(shots, `impressions-${name}.png`) });
    expect(errors).toEqual([]);
    await context.close();
  }
});

test("missing evidence gives actionable setup states and CSV uploads refresh the link axis", async ({
  page,
}) => {
  await login(page);
  await page.goto("/sites/site2?tab=analysis");
  for (const axis of axes.filter((key) => key !== "site-links")) {
    const section = page.getByTestId(`axis-${axis}`);
    await expect(section.locator(".badge")).toHaveText("Needs setup");
    await expect(section.locator(".axis-reason")).not.toBeEmpty();
    await expect(section.getByTestId("axis-empty").first()).toBeAttached();
  }
  await page.goto("/sites/arlington?tab=analysis");
  const section = page.getByTestId("axis-internal-links");
  await section
    .getByLabel(/Site Audit CSV/)
    .setInputFiles({
      name: "audit.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "URL,Inlinks,HTTP status code\nhttps://arlington247lockrepair.com/,2,200\nhttps://arlington247lockrepair.com/uploaded-orphan,0,200\n",
      ),
    });
  await section.getByRole("button", { name: "Upload export" }).click();
  await expect(section.getByRole("status")).toContainText("Export saved");
  await expect(
    section.getByRole("table", { name: "Orphan candidates", exact: true }),
  ).toContainText("uploaded-orphan");
  await page.goto(
    "/sites/arlington?tab=analysis&start=2020-01-01&end=2020-01-02",
  );
  await expect(
    page.getByTestId("axis-impressions-clicks").locator(".badge"),
  ).toHaveText("Needs setup");
});
