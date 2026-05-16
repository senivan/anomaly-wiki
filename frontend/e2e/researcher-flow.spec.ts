import { expect, test } from "@playwright/test";
import {
  authenticate,
  loginApi,
  registerUser,
  uniqueId,
  waitForSearchHit,
} from "./helpers";

test("researcher creates, edits, searches, and reopens a wiki page @mobile", async ({ page, request }) => {
  const { email } = await registerUser(request);
  const token = await loginApi(request, email);
  const slug = uniqueId("e2e-daily");
  const title = `E2E Daily ${slug}`;

  await authenticate(page, token);
  await page.goto("/edit/new");
  await page.getByLabel("Slug (URL identifier)").fill(slug);
  await page.getByLabel("Type").selectOption("Anomaly");
  await page.getByLabel("Visibility").selectOption("Public");
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Summary").fill("E2E daily flow summary.");
  await page.locator("textarea.edit-textarea").fill("## Observations\n\nThe frontend created this record.");
  await page.getByRole("button", { name: /Create record/ }).click();

  await expect(page).toHaveURL(new RegExp(`/wiki/${slug}$`));
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("E2E daily flow summary.")).toBeVisible();
  await expect(page.getByRole("definition").filter({ hasText: /^Draft$/ })).toBeVisible();
  await expect(page.getByRole("definition").filter({ hasText: /^Public$/ })).toBeVisible();
  await expect(page.getByText("The frontend created this record.")).toBeVisible();

  await page.getByRole("link", { name: /Edit/ }).first().click();
  await page.locator("textarea.edit-textarea").fill("## Observations\n\nThe draft was updated by Playwright.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  await waitForSearchHit(request, token, title, slug);
  await page.goto(`/search?q=${encodeURIComponent(title)}`);
  await expect(page.getByText(`${title}`)).toBeVisible();
  await expect(page.getByText("No records match")).toHaveCount(0);
  await page.getByText(title).click();
  await expect(page).toHaveURL(new RegExp(`/wiki/${slug}$`));
});
