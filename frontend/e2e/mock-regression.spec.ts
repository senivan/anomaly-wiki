import { expect, test } from "@playwright/test";
import { authenticate, loginApi, promoteUser, registerUser } from "./helpers";

test("clean media and review screens do not render hardcoded mock records", async ({ page, request }) => {
  const editor = await registerUser(request);
  promoteUser(editor.email, "Editor");
  const token = await loginApi(request, editor.email);
  await authenticate(page, token);

  await page.goto("/media");
  await expect(page.getByText("AN-047_funnel_perimeter_01.jpg")).toHaveCount(0);
  await expect(page.getByText("gravity-funnel")).toHaveCount(0);

  await page.goto("/review");
  await expect(page.getByText("incident-2026-04-22")).toHaveCount(0);
  await expect(page.getByText("compass-fault")).toHaveCount(0);
});

test("mobile navigation can reach login, search, and wiki read @mobile", async ({ page, request }) => {
  const researcher = await registerUser(request);
  const token = await loginApi(request, researcher.email);
  const slug = `mobile-${Date.now()}`;

  await authenticate(page, token);
  await page.goto("/");
  await expect(page.getByText("Search")).toBeVisible();
  await page.goto(`/search?q=${encodeURIComponent("nothing")}`);
  await expect(page.getByRole("heading", { name: "Search the archive" })).toBeVisible();

  const created = await request.post(`${process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://127.0.0.1:8000"}/pages`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      slug,
      type: "Article",
      visibility: "Public",
      title: "Mobile E2E Read",
      summary: "Mobile smoke summary.",
      content: "Mobile smoke content.",
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  await page.goto(`/wiki/${slug}`);
  await expect(page.getByRole("heading", { name: "Mobile E2E Read" })).toBeVisible();
});
