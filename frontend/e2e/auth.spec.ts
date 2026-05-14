import { expect, test } from "@playwright/test";
import { password, uniqueId } from "./helpers";

test("registers, logs in, and logs out through the UI @mobile", async ({ page }) => {
  const email = `${uniqueId("auth")}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/login\?redirect=\//);

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(".sidebar .nav-item").filter({ hasText: /^My drafts$/ })).toBeVisible();
  await expect(page.getByText("Researcher · L2")).toBeVisible();

  await page.locator(".topbar__user button").click();
  await page.goto("/drafts");
  await expect(page).toHaveURL(/\/login\?redirect=%2Fdrafts/);
});
