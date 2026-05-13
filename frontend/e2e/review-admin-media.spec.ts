import { expect, test } from "@playwright/test";
import {
  authenticate,
  createPage,
  loginApi,
  password,
  promoteUser,
  registerUser,
  transitionStatus,
  uniqueId,
} from "./helpers";

test("editor publishes a review-state page from the UI", async ({ page, request }) => {
  const researcher = await registerUser(request);
  const editor = await registerUser(request);
  promoteUser(editor.email, "Editor");

  const researcherToken = await loginApi(request, researcher.email);
  const editorToken = await loginApi(request, editor.email);
  const { slug, state } = await createPage(request, researcherToken, {
    title: `E2E Review ${uniqueId("publish")}`,
    content: "## Review\n\nReady for editor approval.",
  });
  await transitionStatus(request, researcherToken, state.page.id, state.page.version, "Review");

  await authenticate(page, editorToken);
  await page.goto(`/wiki/${slug}`);
  await expect(page.getByRole("button", { name: /Publish/ })).toBeVisible();
  await page.getByRole("button", { name: /Publish/ }).click();
  await expect(page.getByText("Published")).toBeVisible();
});

test("admin changes a user role and the new role takes effect on next login", async ({ page, request }) => {
  const admin = await registerUser(request);
  const researcher = await registerUser(request);
  promoteUser(admin.email, "Admin");
  const adminToken = await loginApi(request, admin.email);

  await authenticate(page, adminToken);
  await page.goto("/admin");
  const row = page.getByRole("row").filter({ hasText: researcher.email });
  await expect(row).toBeVisible();
  await row.getByRole("combobox").selectOption("Editor");
  await row.getByRole("button", { name: "Apply" }).click();
  await expect(row.getByRole("combobox")).toHaveValue("Editor");
  await expect(page.getByText("Role changes take effect on the user's next login")).toBeVisible();

  await page.locator(".topbar__user button").click();
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.getByLabel("Email").fill(researcher.email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Editor · L2")).toBeVisible();
});

test("media library uploads real assets and does not show fixture mocks", async ({ page, request }) => {
  const researcher = await registerUser(request);
  const token = await loginApi(request, researcher.email);
  const fileName = `${uniqueId("asset")}.txt`;

  await authenticate(page, token);
  await page.goto("/media");
  await expect(page.getByText("AN-047_funnel_perimeter_01.jpg")).toHaveCount(0);
  await page.getByLabel("Upload media file").setInputFiles({
    name: fileName,
    mimeType: "text/plain",
    buffer: Buffer.from("playwright media fixture\n"),
  });
  await expect(page.getByText(fileName)).toBeVisible();
});
